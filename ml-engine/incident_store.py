"""
incident_store.py

The "Storage" half of the Correlation & Storage Layer from the
architecture diagram.

Takes Incident objects (produced by correlation_engine.py) and
persists them in MongoDB, so they survive past a single script run
and can later be queried by the Root Cause Analysis layer, the LLM
Explanation layer, and the React dashboard.

Connects to a LOCAL MongoDB instance by default (mongodb://localhost:27017).
If you're running MongoDB inside Minikube/Kubernetes instead of locally,
just change MONGO_URI below.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import timedelta

from correlation_engine import Incident


MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "chaos_healer"
COLLECTION_NAME = "incidents"


class IncidentStore:
    """
    Thin wrapper around a MongoDB collection, specifically for
    storing and retrieving Incident objects. Keeping this isolated
    means the rest of the pipeline never has to know it's MongoDB
    underneath — if that ever changes, only this file changes.
    """

    def __init__(self, uri: str = MONGO_URI, db_name: str = DB_NAME):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[db_name]
        self.collection = self.db[COLLECTION_NAME]

    def is_connected(self) -> bool:
        """Quick check so callers can fail gracefully with a clear message."""
        try:
            self.client.admin.command("ping")
            return True
        except ConnectionFailure:
            return False

    def save_incident(self, incident: Incident) -> str:
        """
        Inserts one incident. Uses incident_id as the unique key so
        re-running detection on the same window doesn't create
        duplicate records.
        """
        doc = incident.to_dict()
        self.collection.update_one(
            {"incident_id": doc["incident_id"]},
            {"$set": doc},
            upsert=True,
        )
        return doc["incident_id"]

    def save_many(self, incidents: list[Incident]) -> int:
        """Bulk save, returns count of incidents written."""
        for incident in incidents:
            self.save_incident(incident)
        return len(incidents)

    def save_diagnosis(self, incident_id: str, diagnosis: dict) -> None:
        """
        Attaches an RCA/LLM diagnosis to an existing incident document.
        Upserts so this also works if the incident wasn't saved separately
        beforehand (e.g. if you only ran rca_engine.py standalone).
        """
        self.collection.update_one(
            {"incident_id": incident_id},
            {"$set": {"diagnosis": diagnosis}},
            upsert=True,
        )

    def get_recent_incidents(self, limit: int = 20) -> list[dict]:
        """Fetch the most recent incidents, newest first."""
        cursor = self.collection.find().sort("start_time", -1).limit(limit)
        return list(cursor)

    def get_by_severity(self, severity: str) -> list[dict]:
        """e.g. get_by_severity('high') for only the serious ones."""
        cursor = self.collection.find({"max_severity": severity})
        return list(cursor)


if __name__ == "__main__":
    # End-to-end sanity check: generate mock metrics -> detect anomalies
    # -> correlate into incidents -> save to MongoDB -> read them back.
    from anomaly_detector import AnomalyDetector, generate_mock_metrics
    from correlation_engine import CorrelationEngine

    store = IncidentStore()

    if not store.is_connected():
        print("Could not connect to MongoDB at", MONGO_URI)
        print("Make sure your local MongoDB service is running, then re-run this file.")
        exit(1)

    print("Connected to MongoDB successfully.\n")

    # Run the full pipeline so far
    data = generate_mock_metrics()
    feature_cols = ["cpu_percent", "memory_percent", "error_rate"]

    detector = AnomalyDetector(contamination=0.05)
    detector.fit(data, feature_columns=feature_cols)
    anomalies = detector.score_batch(data)

    engine = CorrelationEngine(time_window=timedelta(minutes=3))
    incidents = engine.correlate(anomalies)

    saved_count = store.save_many(incidents)
    print(f"Saved {saved_count} incidents to MongoDB.\n")

    print("Reading back the 5 most recent incidents:")
    for doc in store.get_recent_incidents(limit=5):
        print(
            f"  {doc['incident_id']} | {doc['start_time']} | "
            f"severity={doc['max_severity']} | confidence={doc['avg_confidence']}"
        )