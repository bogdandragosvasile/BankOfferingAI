"""Airflow DAG: daily customer profile pipeline.

Task sequence:
    extract_features -> compute_profiles -> load_to_feature_store -> trigger_scoring

1. extract_features: Pull transactions and raw customer data from PostgreSQL.
2. compute_profiles: Normalise, validate, and aggregate into customer profiles.
3. load_to_feature_store: Materialise feature vectors into Feast online store.
4. trigger_scoring: Kick off the offer scoring pipeline via BashOperator.

Drift detection runs as a branch after load_to_feature_store; model retraining
is triggered when drift exceeds the configured threshold.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.trigger_rule import TriggerRule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DAG-level defaults
# ---------------------------------------------------------------------------

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["data-alerts@bank.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------


def extract_features(**context: Any) -> str:
    """Pull the previous day's transactions and customer records from PostgreSQL.

    Returns a JSON string of transaction records serialised through XCom.
    For large volumes, switch the transport layer to S3/GCS.
    """
    execution_date = context["ds"]
    hook = PostgresHook(postgres_conn_id="bank_postgres")

    sql = """
        SELECT transaction_id, customer_id, amount, currency,
               merchant_name, merchant_category_code, transaction_type,
               timestamp, channel, status
        FROM transactions
        WHERE DATE(timestamp) = %s
          AND status = 'completed'
        ORDER BY timestamp
    """
    records = hook.get_records(sql, parameters=[execution_date])
    columns = [
        "transaction_id", "customer_id", "amount", "currency",
        "merchant_name", "merchant_category_code", "transaction_type",
        "timestamp", "channel", "status",
    ]
    rows = [dict(zip(columns, r)) for r in records]
    logger.info("Extracted %d transactions for %s", len(rows), execution_date)

    return json.dumps(rows, default=str)


def compute_profiles(**context: Any) -> str:
    """Normalise raw transactions and compute per-customer profile aggregates.

    Runs the TransactionNormalizer and produces the feature DataFrame that
    will be loaded into Feast.
    """
    from data.kafka.consumers.normalizer import TransactionNormalizer

    raw_json = context["ti"].xcom_pull(task_ids="extract_features")
    raw_records = json.loads(raw_json)

    normalizer = TransactionNormalizer()
    normalized = normalizer.normalize_batch(raw_records)
    logger.info("Normalised %d / %d records", len(normalized), len(raw_records))

    return json.dumps(
        [n.model_dump(mode="json") for n in normalized], default=str
    )


def load_to_feature_store(**context: Any) -> dict[str, Any]:
    """Aggregate normalised transactions into feature vectors and
    materialise them into the Feast online store.

    Falls back to writing a Parquet file if Feast is unavailable.
    """
    import pandas as pd

    raw = context["ti"].xcom_pull(task_ids="compute_profiles")
    records = json.loads(raw)
    if not records:
        logger.warning("No normalised records — skipping feature store load")
        return {"customers_processed": 0}

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["amount_usd"] = pd.to_numeric(df["amount_usd"])

    # Per-customer aggregation
    features = (
        df.groupby("customer_id")
        .agg(
            avg_txn_amount_30d=("amount_usd", "mean"),
            total_spend_30d=("amount_usd", "sum"),
            txn_count_30d=("transaction_id", "count"),
            max_single_txn_30d=("amount_usd", "max"),
            std_txn_amount_30d=("amount_usd", "std"),
        )
        .reset_index()
    )
    features["std_txn_amount_30d"] = features["std_txn_amount_30d"].fillna(0)
    features["feature_timestamp"] = datetime.utcnow()

    # Category distribution
    category_pivot = (
        df.groupby(["customer_id", "merchant_category"])["amount_usd"]
        .sum()
        .unstack(fill_value=0)
    )
    category_totals = category_pivot.sum(axis=1)
    category_pct = (
        category_pivot.div(category_totals, axis=0)
        .add_prefix("category_")
        .add_suffix("_pct")
        .reset_index()
    )
    features = features.merge(category_pct, on="customer_id", how="left")

    # Materialise to Feast
    try:
        from feast import FeatureStore

        store = FeatureStore(repo_path="data/feature_store")
        store.push("transaction_push", features)
        logger.info("Pushed features for %d customers to Feast", len(features))
    except Exception:
        logger.exception("Failed to push features to Feast — falling back to parquet")
        features.to_parquet(
            "data/feature_store/data/customer_transaction_features.parquet",
            index=False,
        )

    return {"customers_processed": len(features)}


def check_data_drift(**context: Any) -> str:
    """Detect feature drift and decide whether to retrain.

    Returns the task_id to follow: ``trigger_retraining`` if drift is
    detected, ``skip_retraining`` otherwise.
    """
    import pandas as pd

    try:
        current = pd.read_parquet(
            "data/feature_store/data/customer_transaction_features.parquet"
        )
    except FileNotFoundError:
        logger.info("No historical features found — skipping drift check")
        return "skip_retraining"

    drift_detected = False
    for col in ["avg_txn_amount_30d", "total_spend_30d", "txn_count_30d"]:
        if col not in current.columns:
            continue
        mean = current[col].mean()
        std = current[col].std()
        if std > 0 and abs(mean) > 0:
            cv = std / abs(mean)
            if cv > 1.5:
                logger.warning("Drift detected on %s (CV=%.2f)", col, cv)
                drift_detected = True

    return "trigger_retraining" if drift_detected else "skip_retraining"


def trigger_retraining(**context: Any) -> None:
    """Kick off model retraining (calls the ML training pipeline)."""
    from airflow.api.common.trigger_dag import trigger_dag

    trigger_dag(
        dag_id="model_retraining_dag",
        run_id=f"drift_retrain_{context['ds']}",
        conf={"trigger_reason": "data_drift"},
        execution_date=context["execution_date"],
        replace_microseconds=False,
    )
    logger.info("Triggered model retraining due to data drift")


def skip_retraining(**context: Any) -> None:
    logger.info("No drift detected — skipping retraining for %s", context["ds"])


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="customer_profile_pipeline",
    default_args=default_args,
    description=(
        "Daily pipeline: extract_features -> compute_profiles -> "
        "load_to_feature_store -> trigger_scoring"
    ),
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["customer", "features", "ml"],
    max_active_runs=1,
) as dag:

    # 1. Extract raw transaction and customer feature data
    t_extract_features = PythonOperator(
        task_id="extract_features",
        python_callable=extract_features,
    )

    # 2. Normalise and compute customer profiles
    t_compute_profiles = PythonOperator(
        task_id="compute_profiles",
        python_callable=compute_profiles,
    )

    # 3. Materialise feature vectors into Feast feature store
    t_load_to_feature_store = PythonOperator(
        task_id="load_to_feature_store",
        python_callable=load_to_feature_store,
    )

    # 4. Trigger the downstream offer scoring pipeline
    t_trigger_scoring = BashOperator(
        task_id="trigger_scoring",
        bash_command=(
            "curl -s -X POST "
            "http://bankoffer-api.bankoffer-prod.svc.cluster.local:8000/internal/scoring/trigger "
            "-H 'Content-Type: application/json' "
            "-d '{\"execution_date\": \"{{ ds }}\", \"source\": \"airflow\"}' "
            "&& echo 'Scoring pipeline triggered successfully'"
        ),
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # 4b. Check for feature drift and conditionally retrain
    t_drift = BranchPythonOperator(
        task_id="check_data_drift",
        python_callable=check_data_drift,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    t_retrain = PythonOperator(
        task_id="trigger_retraining",
        python_callable=trigger_retraining,
    )

    t_skip = PythonOperator(
        task_id="skip_retraining",
        python_callable=skip_retraining,
    )

    # DAG wiring: main path
    t_extract_features >> t_compute_profiles >> t_load_to_feature_store
    # Parallel branches after feature store load
    t_load_to_feature_store >> [t_trigger_scoring, t_drift]
    # Drift branch
    t_drift >> [t_retrain, t_skip]
