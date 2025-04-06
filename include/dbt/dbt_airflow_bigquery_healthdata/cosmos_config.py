from cosmos.config import ProfileConfig, ProjectConfig
from pathlib import Path

DBT_CONFIG = ProfileConfig(
    profile_name='dbt_airflow_bigquery_healthdata',
    target_name='prod',
    # target_name='dev',
    profiles_yml_filepath=Path('/usr/local/airflow/include/dbt/dbt_airflow_bigquery_healthdata/profiles.yml')
)

DBT_PROJECT_CONFIG = ProjectConfig(
    dbt_project_path='/usr/local/airflow/include/dbt/dbt_airflow_bigquery_healthdata/'
)
