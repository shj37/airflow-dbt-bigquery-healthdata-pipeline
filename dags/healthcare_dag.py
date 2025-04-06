from airflow.decorators import dag
from pendulum import datetime
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.models import Variable
from cosmos.airflow.task_group import DbtTaskGroup
from include.dbt.dbt_airflow_bigquery_healthdata.cosmos_config import DBT_CONFIG, DBT_PROJECT_CONFIG
from cosmos.constants import LoadMode
from cosmos.config import RenderConfig

PATH_TO_DATA_SCRIPT = "/usr/local/airflow/include/healthcare_data.py"
PATH_TO_DEV_SQL_SCRIPT = "/usr/local/airflow/include/create_external_tables.sql" 

GCP_CONN_ID = Variable.get("GCP_CONN_ID", default_var="gcp")

TARGET_ENV = DBT_CONFIG.target_name
CREATE_EXTERNAL_TABLES_SQL = f"""
    -- Creating patient_data external table (CSV format)
    CREATE OR REPLACE EXTERNAL TABLE `dbt-health-data-project.airflow_{TARGET_ENV.lower()}_healthcare_data.patient_data_external`
    OPTIONS (
    format = 'CSV',
    uris = ['gs://health-data-bucket-ju/{TARGET_ENV.lower()}/patient_data.csv'],
    skip_leading_rows = 1
    );

    -- Creating ehr_data external table (JSON format)
    CREATE OR REPLACE EXTERNAL TABLE `dbt-health-data-project.airflow_{TARGET_ENV.lower()}_healthcare_data.ehr_data_external`
    OPTIONS (
    format = 'NEWLINE_DELIMITED_JSON',
    uris = ['gs://health-data-bucket-ju/{TARGET_ENV.lower()}/ehr_data.json']
    );

    -- Creating claims_data external table (Parquet format with explicit schema)
    CREATE OR REPLACE EXTERNAL TABLE `dbt-health-data-project.airflow_{TARGET_ENV.lower()}_healthcare_data.claims_data_external`
    OPTIONS (
    format = 'PARQUET',
    uris = ['gs://health-data-bucket-ju/{TARGET_ENV.lower()}/claims_data.parquet']
    );
    """

@dag(
    # schedule=None,
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["healthcare"],
    doc_md=__doc__,
)
def dbt_healthcare_pipeline():
    generate_data = BashOperator(
        task_id="generate_data",
        bash_command=f"python {PATH_TO_DATA_SCRIPT}"
    )

    create_external_tables = BigQueryInsertJobOperator(
        task_id="create_external_tables",
        configuration={
            "query": {
                "query": CREATE_EXTERNAL_TABLES_SQL,
                "useLegacySql": False,
            }
        },
        location="us-central1",  
        gcp_conn_id=GCP_CONN_ID,
    )

    dbt_test_raw = BashOperator(
        task_id="dbt_test_raw",
        bash_command="source /usr/local/airflow/dbt_venv/bin/activate && dbt test --select source:*",
        cwd="/usr/local/airflow/include/dbt/dbt_airflow_bigquery_healthdata"
    )

    if TARGET_ENV == 'dev':
        generate_data >> create_external_tables >> dbt_test_raw
    else:
        generate_data >> create_external_tables

    transform = DbtTaskGroup(
        group_id="transform",
        project_config=DBT_PROJECT_CONFIG,
        profile_config=DBT_CONFIG,
        render_config=RenderConfig(
            load_method=LoadMode.DBT_LS,
            select=['path:models'],
            dbt_executable_path="source /usr/local/airflow/dbt_venv/bin/activate && /usr/local/airflow/include/dbt/dbt_airflow_bigquery_healthdata"
        )
    )

    if TARGET_ENV == 'dev':
        dbt_test_raw >> transform
    else:
        create_external_tables >> transform

dbt_healthcare_pipeline()