#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Example Airflow DAG that uses Google AutoML services.
"""
import os
from datetime import datetime

from airflow import models
from airflow.providers.google.cloud.hooks.automl import CloudAutoMLHook
from airflow.providers.google.cloud.operators.automl import (
    AutoMLCreateDatasetOperator,
    AutoMLDeleteDatasetOperator,
    AutoMLDeleteModelOperator,
    AutoMLImportDataOperator,
    AutoMLTrainModelOperator,
)
from airflow.utils.trigger_rule import TriggerRule

ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "example_automl_vision"

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
GCP_AUTOML_LOCATION = os.environ.get("GCP_AUTOML_LOCATION", "us-central1")
GCP_AUTOML_VISION_BUCKET = os.environ.get("GCP_AUTOML_VISION_BUCKET", "gs://INVALID BUCKET NAME")

# Example values
DATASET_ID = "ICN123455678"

# Example model
MODEL = {
    "display_name": "auto_model_2",
    "dataset_id": DATASET_ID,
    "image_classification_model_metadata": {"train_budget": 1},
}

# Example dataset
DATASET = {
    "display_name": "test_vision_dataset",
    "image_classification_dataset_metadata": {"classification_type": "MULTILABEL"},
}

IMPORT_INPUT_CONFIG = {"gcs_source": {"input_uris": [GCP_AUTOML_VISION_BUCKET]}}

extract_object_id = CloudAutoMLHook.extract_object_id

# Example DAG for AutoML Vision Classification
with models.DAG(
    DAG_ID,
    schedule="@once",  # Override to match your needs
    start_date=datetime(2021, 1, 1),
    catchup=False,
    user_defined_macros={"extract_object_id": extract_object_id},
    tags=['example', 'automl'],
) as dag:
    create_dataset_task = AutoMLCreateDatasetOperator(
        task_id="create_dataset_task", dataset=DATASET, location=GCP_AUTOML_LOCATION
    )

    dataset_id = create_dataset_task.output["dataset_id"]

    import_dataset_task = AutoMLImportDataOperator(
        task_id="import_dataset_task",
        dataset_id=dataset_id,
        location=GCP_AUTOML_LOCATION,
        input_config=IMPORT_INPUT_CONFIG,
    )

    MODEL["dataset_id"] = dataset_id

    create_model = AutoMLTrainModelOperator(task_id="create_model", model=MODEL, location=GCP_AUTOML_LOCATION)

    model_id = create_model.output["model_id"]

    delete_model_task = AutoMLDeleteModelOperator(
        task_id="delete_model_task",
        model_id=model_id,
        location=GCP_AUTOML_LOCATION,
        project_id=GCP_PROJECT_ID,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    delete_datasets_task = AutoMLDeleteDatasetOperator(
        task_id="delete_datasets_task",
        dataset_id=dataset_id,
        location=GCP_AUTOML_LOCATION,
        project_id=GCP_PROJECT_ID,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    (
        # TEST SETUP
        create_dataset_task
        >> import_dataset_task
        # TEST BODY
        >> create_model
        # TEST TEARDOWN
        >> delete_model_task
        >> delete_datasets_task
    )

    from tests.system.utils.watcher import watcher

    # This test needs watcher in order to properly mark success/failure
    # when "tearDown" task with trigger rule is part of the DAG
    list(dag.tasks) >> watcher()

from tests.system.utils import get_test_run  # noqa: E402

# Needed to run the example DAG with pytest (see: tests/system/README.md#run_via_pytest)
test_run = get_test_run(dag)
