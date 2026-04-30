"""
Seed fake student profiles into the TeamUp database.

Creates realistic users with skills, intents, connections, and messages
so the app looks populated for demos / professor presentations.

Usage (from inside the backend container or with venv active):
    python manage.py shell < seed_fake_data.py
  OR
    python seed_fake_data.py   (if run directly from backend/)

Run: docker compose exec backend python seed_fake_data.py
"""

import os
import sys
import django

# ── Django setup ─────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "student_collab.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import random
import uuid
import requests
from django.contrib.auth.hashers import make_password
from core.models import User, Profile, Connection, Message

ML_SERVICE_URL = "http://ml-service:8001"


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        f"{ML_SERVICE_URL}/batch_embed",
        json={"texts": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]

# ── Fake data pools ───────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Priya", "Lucas", "Emma", "Wei", "Sofia", "Kofi", "Amara",
    "Mateo", "Yuki", "Ravi", "Nadia", "Felix", "Ingrid", "Omar", "Fatima",
    "Alex", "Jordan", "Morgan", "Taylor", "Sam", "Jamie", "Riley", "Quinn",
    "Arjun", "Mei", "Elena", "Ivan", "Aisha", "Lena", "Hassan", "Vera",
]

LAST_NAMES = [
    "Chen", "Patel", "Garcia", "Smith", "Kim", "Johnson", "Nguyen", "Brown",
    "Martinez", "Wilson", "Thompson", "Davis", "Anderson", "Taylor", "Lewis",
    "Walker", "Harris", "Clark", "Robinson", "Lee", "Turner", "Mitchell",
    "Phillips", "Parker", "Evans", "Stewart", "Sanchez", "Reed", "Baker",
]

PROFILES = [
    {
        "department": "Computer Science",
        "skills": "Python, machine learning, PyTorch, REST APIs, PostgreSQL, Docker",
        "intent": "Build a real-time recommendation system using collaborative filtering for personalized content discovery",
    },
    {
        "department": "Computer Science",
        "skills": "Java, distributed systems, Apache Kafka, Kubernetes, Spring Boot, microservices",
        "intent": "Develop a distributed key-value store with consistent hashing and automatic fault tolerance",
    },
    {
        "department": "Computer Science",
        "skills": "JavaScript, TypeScript, React, Node.js, GraphQL, MongoDB, AWS Lambda",
        "intent": "Create a full-stack collaborative coding platform with real-time pair programming support",
    },
    {
        "department": "Computer Science",
        "skills": "Python, NLP, BERT, transformers, spaCy, Hugging Face, RAG pipelines",
        "intent": "Build an intelligent question-answering system over academic research papers",
    },
    {
        "department": "Computer Science",
        "skills": "Scala, Apache Spark, Hadoop, data pipelines, stream processing, Delta Lake",
        "intent": "Develop a large-scale data pipeline for processing and analyzing social network graphs",
    },
    {
        "department": "Data Science",
        "skills": "Python, pandas, scikit-learn, XGBoost, feature engineering, SHAP, A/B testing",
        "intent": "Build a churn prediction model with causal inference to identify preventable user attrition",
    },
    {
        "department": "Data Science",
        "skills": "R, Stan, Bayesian statistics, MCMC, causal inference, difference-in-differences",
        "intent": "Develop a probabilistic demand forecasting system with uncertainty quantification",
    },
    {
        "department": "Data Science",
        "skills": "Python, PySpark, Databricks, Delta Lake, dbt, Airflow, BigQuery, Snowflake",
        "intent": "Create an end-to-end MLOps platform covering training, deployment, monitoring, and retraining",
    },
    {
        "department": "Electrical Engineering",
        "skills": "VHDL, FPGA design, Xilinx Vivado, digital signal processing, RTL synthesis, Verilog",
        "intent": "Design an FPGA-accelerated neural network inference engine for real-time video analytics",
    },
    {
        "department": "Electrical Engineering",
        "skills": "Embedded C, ARM Cortex-M, FreeRTOS, I2C, SPI, UART, CAN bus, power management",
        "intent": "Build a low-power IoT sensor node with edge ML inference for industrial predictive maintenance",
    },
    {
        "department": "Mechanical Engineering",
        "skills": "SolidWorks, AutoCAD, FEA analysis, ANSYS Mechanical, topology optimization, GD&T",
        "intent": "Design a compliant soft robotic gripper for gentle manipulation of fragile objects",
    },
    {
        "department": "Mechanical Engineering",
        "skills": "ROS, robot kinematics, dynamics, motion planning, MoveIt, mechatronics, URDF",
        "intent": "Build a model predictive control system for a six-axis robot with real-time collision avoidance",
    },
    {
        "department": "Biomedical Engineering",
        "skills": "Python, bioinformatics, RNA-seq, Biopython, GATK, variant calling, scRNA-seq",
        "intent": "Develop a deep learning pipeline for early cancer detection in histopathology images",
    },
    {
        "department": "Biomedical Engineering",
        "skills": "Python, EEG signal processing, brain-computer interfaces, biosensor design, spike sorting",
        "intent": "Build a wearable ECG monitor with real-time arrhythmia detection using edge machine learning",
    },
    {
        "department": "Physics",
        "skills": "Python, NumPy, SciPy, C++, Monte Carlo simulation, ROOT, particle physics, GEANT4",
        "intent": "Develop a machine learning classifier for exotic particle identification in LHC collision datasets",
    },
    {
        "department": "Mathematics",
        "skills": "Python, numerical analysis, convex optimization, CVXPY, interior point methods, ADMM",
        "intent": "Develop efficient first-order algorithms for large-scale semidefinite programming in ML",
    },
    {
        "department": "Environmental Science",
        "skills": "Python, Google Earth Engine, multispectral imagery, land cover classification, NDVI, SAR",
        "intent": "Develop a deep learning deforestation monitor using weekly satellite imagery with real-time alerting",
    },
    {
        "department": "Neuroscience",
        "skills": "Python, MNE, spike sorting, Kilosort, calcium imaging, optogenetics, patch clamp",
        "intent": "Build a neural population decoder translating motor cortex activity into prosthetic control",
    },
    {
        "department": "Economics",
        "skills": "Python, R, econometrics, panel data, instrumental variables, causal inference, Stata",
        "intent": "Build a causal inference framework for evaluating wage returns of online education interventions",
    },
    {
        "department": "Civil Engineering",
        "skills": "AutoCAD, SAP2000, structural analysis, reinforced concrete design, seismic detailing, BIM",
        "intent": "Develop a structural health monitoring system using distributed sensors and ML for bridge damage detection",
    },
]

MESSAGES = [
    "Hey! I saw your profile and I think we could build something great together.",
    "Your skills in machine learning look amazing. I'm working on a similar project!",
    "Would you be interested in collaborating on my thesis project?",
    "I've been looking for someone with your background. Let's chat!",
    "I love your project idea. I have some complementary skills that could help.",
    "Hey, are you still looking for collaborators? My work aligns well with yours.",
    "Just connected with you — excited to explore potential collaboration!",
    "Saw you're also working on NLP stuff, would love to exchange ideas.",
    "Your project on distributed systems is exactly what I need help with!",
    "Let's schedule a quick call to see if our projects can align.",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def make_email(name, idx):
    slug = name.lower().replace(" ", ".")
    return f"{slug}.{idx:03d}@university.edu"


# ── Seed ──────────────────────────────────────────────────────────────────────

def seed(n_users=30, n_connections=40, n_messages=60, clear=False):
    if clear:
        print("Clearing existing fake users...")
        User.objects.filter(email__endswith="@university.edu").delete()
        print("  Done.")

    print(f"\nCreating {n_users} fake users...")
    created_users = []
    password_hash = make_password("Password123!")

    for i in range(n_users):
        profile_template = PROFILES[i % len(PROFILES)]
        name = random_name()
        email = make_email(name, i + 1)

        # Skip if already exists
        if User.objects.filter(email=email).exists():
            print(f"  Skipping {email} (already exists)")
            continue

        user = User.objects.create(
            id=uuid.uuid4(),
            email=email,
            username=email,
            name=name,
            password=password_hash,
            is_active=True,
        )

        Profile.objects.create(
            user=user,
            skills_text=profile_template["skills"],
            intent_text=profile_template["intent"],
        )

        created_users.append(user)
        print(f"  [{i+1:02d}] {name} — {profile_template['department']}")

    print(f"\nCreated {len(created_users)} users.")

    # ── Generate embeddings for all seeded profiles ───────────────────────────
    profiles_needing_embeddings = list(
        Profile.objects.filter(
            user__email__endswith="@university.edu",
            skill_embedding__isnull=True,
        ).select_related("user")
    )

    if profiles_needing_embeddings:
        print(f"\nGenerating embeddings for {len(profiles_needing_embeddings)} profiles...")
        try:
            skills = [p.skills_text for p in profiles_needing_embeddings]
            intents = [p.intent_text for p in profiles_needing_embeddings]

            BATCH = 32
            skill_embeddings, intent_embeddings = [], []
            for i in range(0, len(skills), BATCH):
                skill_embeddings.extend(generate_embeddings(skills[i:i+BATCH]))
                intent_embeddings.extend(generate_embeddings(intents[i:i+BATCH]))
                print(f"  Embedded {min(i+BATCH, len(skills))}/{len(skills)} profiles...")

            for profile, se, ie in zip(profiles_needing_embeddings, skill_embeddings, intent_embeddings):
                profile.skill_embedding = se
                profile.intent_embedding = ie

            Profile.objects.bulk_update(profiles_needing_embeddings, ["skill_embedding", "intent_embedding"])
            print(f"  Embeddings saved for {len(profiles_needing_embeddings)} profiles.")
        except Exception as e:
            print(f"  WARNING: Could not generate embeddings — {e}")
            print("  Profiles created but matching won't work until ML service is running.")
            print("  Re-run this script once Docker is up to fill in embeddings.")
    else:
        print("\nAll profiles already have embeddings.")

    # ── Connections ───────────────────────────────────────────────────────────
    all_users = list(User.objects.filter(email__endswith="@university.edu"))
    if len(all_users) < 2:
        print("Not enough users to create connections.")
        return

    print(f"\nCreating {n_connections} connections...")
    connections_made = 0
    attempts = 0

    while connections_made < n_connections and attempts < n_connections * 10:
        attempts += 1
        u1, u2 = random.sample(all_users, 2)
        if Connection.objects.filter(requester=u1, receiver=u2).exists():
            continue
        if Connection.objects.filter(requester=u2, receiver=u1).exists():
            continue

        status = random.choices(
            ["accepted", "accepted", "accepted", "pending", "declined"],
            weights=[50, 50, 50, 30, 10],
            k=1
        )[0]

        conn = Connection.objects.create(requester=u1, receiver=u2, status=status)
        connections_made += 1
        print(f"  {u1.name} → {u2.name} ({status})")

    print(f"Created {connections_made} connections.")

    # ── Messages (only on accepted connections) ───────────────────────────────
    accepted = list(Connection.objects.filter(
        requester__email__endswith="@university.edu",
        status="accepted"
    ))

    if not accepted:
        print("\nNo accepted connections to add messages to.")
        return

    print(f"\nAdding {n_messages} messages to accepted connections...")
    for i in range(n_messages):
        conn = random.choice(accepted)
        sender = random.choice([conn.requester, conn.receiver])
        Message.objects.create(
            connection=conn,
            sender=sender,
            content=random.choice(MESSAGES),
        )

    print(f"Created {n_messages} messages.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SEED COMPLETE")
    print("=" * 50)
    print(f"  Users      : {User.objects.filter(email__endswith='@university.edu').count()}")
    print(f"  Profiles   : {Profile.objects.count()}")
    print(f"  Connections: {Connection.objects.count()}")
    print(f"  Messages   : {Message.objects.count()}")
    print(f"\n  Login with any seeded account:")
    sample = User.objects.filter(email__endswith="@university.edu").first()
    if sample:
        print(f"    Email   : {sample.email}")
        print(f"    Password: Password123!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed fake data into TeamUp DB")
    parser.add_argument("--users", type=int, default=30, help="Number of users to create (default: 30)")
    parser.add_argument("--connections", type=int, default=40, help="Number of connections (default: 40)")
    parser.add_argument("--messages", type=int, default=60, help="Number of messages (default: 60)")
    parser.add_argument("--clear", action="store_true", help="Delete existing fake users first")
    args = parser.parse_args()

    seed(
        n_users=args.users,
        n_connections=args.connections,
        n_messages=args.messages,
        clear=args.clear,
    )
