"""
Synthetic student profile generator for TeamUp benchmarks.

Calls the ML service /batch_embed endpoint to generate real semantic embeddings.
Saves parquet files: data/synthetic_1k.parquet and data/synthetic_10k.parquet

Usage:
    python generate_synthetic_data.py --scale 1000
    python generate_synthetic_data.py --scale 10000
    python generate_synthetic_data.py --scale all
"""

import argparse
import os
import random
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:8001")
OUTPUT_DIR = Path(__file__).parent / "data"
BATCH_SIZE = 64

# ── Department profiles ────────────────────────────────────────────────────────

DEPARTMENTS = {
    "Computer Science": {
        "skills": [
            "Python, machine learning, PyTorch, deep neural networks, data structures, algorithms, REST APIs, PostgreSQL",
            "Java, distributed systems, Apache Kafka, Kubernetes, Docker, Spring Boot, microservices, gRPC, Redis",
            "JavaScript, TypeScript, React, Node.js, GraphQL, MongoDB, CI/CD pipelines, AWS Lambda, serverless",
            "C++, systems programming, CUDA, parallel computing, memory management, OpenMPI, HPC, profiling",
            "Python, natural language processing, BERT, transformers, text classification, spaCy, Hugging Face, RAG",
            "Go, Rust, network programming, protocol buffers, distributed databases, consensus algorithms, Raft",
            "Python, computer vision, OpenCV, YOLO, image segmentation, convolutional neural networks, MediaPipe",
            "Scala, Apache Spark, Hadoop, Flink, data pipelines, stream processing, Delta Lake, data engineering",
            "Python, reinforcement learning, OpenAI Gym, policy gradient, Q-learning, multi-agent simulation",
            "Swift, iOS development, SwiftUI, Core ML, ARKit, mobile architecture, UIKit, CocoaPods",
            "Python, MLOps, Kubeflow, MLflow, model serving, feature stores, data versioning, DVC",
            "Haskell, OCaml, functional programming, type theory, compiler design, LLVM, formal verification",
        ],
        "intents": [
            "Build a real-time recommendation system using collaborative filtering and matrix factorization for personalized content discovery",
            "Develop a distributed key-value store with consistent hashing, replication, and automatic fault tolerance",
            "Create a federated learning platform that enables privacy-preserving model training across edge devices",
            "Build an autonomous code review tool using large language models and static analysis to catch bugs pre-merge",
            "Develop a real-time fraud detection pipeline using graph neural networks on transaction stream data",
            "Create a scalable microservices platform with service mesh, distributed tracing, and intelligent auto-scaling",
            "Build a compiler and runtime for a domain-specific language targeting high-performance scientific computing",
            "Develop a natural language interface for databases that translates English questions to optimized SQL queries",
            "Create a decentralized peer-to-peer file sharing system with content addressing and automatic deduplication",
            "Build a multi-agent simulation environment for training cooperative autonomous vehicle navigation policies",
            "Develop a knowledge graph system that extracts structured information from unstructured scientific papers",
            "Create an intelligent code completion system fine-tuned on domain-specific codebases using retrieval augmentation",
        ],
    },
    "Electrical Engineering": {
        "skills": [
            "VHDL, FPGA design, Xilinx Vivado, digital signal processing, RTL synthesis, timing analysis, Verilog",
            "MATLAB, Simulink, control systems, PID controllers, state space analysis, Kalman filtering, LQR design",
            "PCB design, Altium Designer, analog circuits, RF engineering, impedance matching, LTSpice, signal integrity",
            "Embedded C, ARM Cortex-M, FreeRTOS, device drivers, I2C, SPI, UART, CAN bus, power management",
            "Python, TensorFlow, hardware-software co-design, model compression, FPGA inference acceleration, quantization",
            "Power electronics, DC-DC converters, motor drives, inverter design, GaN transistors, energy harvesting",
            "MATLAB, antenna design, electromagnetic simulation, HFSS, CST, radar systems, phased arrays",
        ],
        "intents": [
            "Design a low-power IoT sensor node with edge ML inference for predictive maintenance in industrial settings",
            "Develop an FPGA-accelerated neural network inference engine achieving real-time throughput for video analytics",
            "Build a wireless power transfer system for implantable medical devices meeting biocompatibility standards",
            "Create an adaptive power management system for renewable energy microgrids with intelligent battery control",
            "Develop a high-precision motor control system with torque ripple minimization for robotic surgical instruments",
            "Design a software-defined radio platform for cognitive spectrum sensing and dynamic frequency access",
            "Build a 5G mmWave phased array antenna system with beamforming for indoor positioning accuracy under 10cm",
        ],
    },
    "Mechanical Engineering": {
        "skills": [
            "SolidWorks, AutoCAD, FEA analysis, ANSYS Mechanical, topology optimization, GD&T, machining processes",
            "MATLAB, Python, CFD, OpenFOAM, turbulence modeling, conjugate heat transfer, multiphase flow",
            "ROS, robot kinematics, dynamics, motion planning, MoveIt, servo systems, mechatronics, URDF",
            "3D printing, composite materials design, materials science, fatigue analysis, fracture mechanics, DIC",
            "CAD/CAM, CNC programming, injection molding design, sheet metal, tolerance analysis, DFM principles",
            "MATLAB, control systems, vibration analysis, structural dynamics, modal analysis, active noise control",
        ],
        "intents": [
            "Design a compliant soft robotic gripper using pneumatic actuators for gentle manipulation of fragile objects",
            "Develop a computational topology optimization framework for lightweight aerospace structural components",
            "Build an autonomous underwater vehicle for deep-sea oceanographic sampling with minimal power consumption",
            "Create a generative design pipeline for spacecraft bracket optimization meeting mass and stiffness constraints",
            "Develop a multi-physics simulation framework for predicting thermal-mechanical fatigue in gas turbine coatings",
            "Build a model predictive control system for a six-axis industrial robot with real-time collision avoidance",
        ],
    },
    "Biomedical Engineering": {
        "skills": [
            "Python, bioinformatics, BLAST, genome assembly, RNA-seq, Biopython, GATK, variant calling, scRNA-seq",
            "MATLAB, Python, medical image processing, MRI reconstruction, CT segmentation, ITK, biostatistics",
            "Machine learning, protein structure prediction, AlphaFold, drug discovery, molecular docking, cheminformatics",
            "Lab techniques, CRISPR-Cas9, cell culture, flow cytometry, qPCR, Western blot, confocal microscopy",
            "Python, EEG/ECG signal processing, brain-computer interfaces, biosensor design, spike sorting, LFP analysis",
            "MATLAB, biomechanics, musculoskeletal modeling, OpenSim, gait analysis, prosthetics design, FEA",
        ],
        "intents": [
            "Develop a deep learning pipeline for early cancer detection in histopathology whole-slide images",
            "Build a wearable ECG monitor with real-time arrhythmia detection and alert using edge machine learning",
            "Create a graph neural network model for predicting protein-drug binding affinities in virtual screening",
            "Design a microfluidic lab-on-chip device for point-of-care diagnostics of sepsis biomarkers",
            "Develop a brain-computer interface enabling communication for ALS patients using imagined speech decoding",
            "Build a patient-specific surgical planning tool combining CT segmentation, FEA, and AR visualization",
        ],
    },
    "Data Science": {
        "skills": [
            "Python, pandas, scikit-learn, XGBoost, LightGBM, feature engineering, SHAP, model monitoring, A/B testing",
            "R, Stan, Bayesian statistics, MCMC, causal inference, instrumental variables, difference-in-differences",
            "Python, TensorFlow, Keras, neural architecture search, AutoML, hyperparameter optimization, Optuna",
            "SQL, dbt, Airflow, data warehousing, Kimball modeling, BigQuery, Snowflake, dbt, Fivetran",
            "Python, NLP, topic modeling, LDA, BERTopic, sentiment analysis, named entity recognition, text mining",
            "PySpark, Databricks, Delta Lake, data quality, great_expectations, ETL design, data mesh architecture",
            "Python, time series, Prophet, ARIMA, LSTM, anomaly detection, seasonal decomposition, forecasting",
        ],
        "intents": [
            "Build a churn prediction model with causal inference components to identify preventable customer attrition",
            "Develop a probabilistic electricity demand forecasting system with uncertainty quantification for grid operators",
            "Create an end-to-end MLOps platform covering training, versioning, deployment, monitoring, and retraining",
            "Build a hierarchical demand forecasting system for retail inventory optimization across thousands of SKUs",
            "Develop a survival analysis pipeline for clinical trial outcome prediction using electronic health records",
            "Create a real-time personalization engine combining collaborative filtering with contextual bandit exploration",
        ],
    },
    "Physics": {
        "skills": [
            "Python, NumPy, SciPy, C++, Monte Carlo simulation, ROOT, particle physics detector analysis, GEANT4",
            "Python, Qiskit, quantum computing, quantum error correction, variational quantum algorithms, quantum ML",
            "Python, astrophysics data analysis, FITS, Astropy, radio telescope processing, pulsar timing, VLBI",
            "C++, GEANT4, detector simulation, HEP analysis, collider data processing, CERN ROOT, machine learning",
            "Python, DFT calculations, VASP, molecular dynamics, LAMMPS, Materials Project API, phonon calculations",
            "MATLAB, Python, plasma physics, MHD simulation, spectroscopy, laser physics, ultrafast optics",
        ],
        "intents": [
            "Develop a machine learning classifier for exotic particle identification in LHC Run 3 collision datasets",
            "Build a variational quantum eigensolver optimizer for quantum chemistry calculations on NISQ hardware",
            "Create a gravitational wave signal detection pipeline using matched filtering combined with deep learning",
            "Develop a neural network interatomic potential for accelerating ab initio molecular dynamics of oxides",
            "Build an automated radio transient classification pipeline for the Square Kilometre Array survey data",
            "Create a physics-informed neural network solver for nonlinear plasma wave propagation in fusion devices",
        ],
    },
    "Economics": {
        "skills": [
            "Python, R, econometrics, panel data, instrumental variables, regression discontinuity, difference-in-differences",
            "Stata, MATLAB, time series, VAR models, VECM, cointegration, GARCH, structural breaks, forecasting",
            "Python, agent-based modeling, Mesa, game theory, mechanism design, auction theory, matching markets",
            "R, causal inference, propensity score matching, synthetic control, natural experiments, policy evaluation",
            "Python, financial econometrics, portfolio optimization, risk models, factor investing, Fama-French, alpha",
            "Python, network economics, IO models, demand estimation, BLP, market power, antitrust analysis",
        ],
        "intents": [
            "Build an agent-based market microstructure model to study high-frequency trading and price formation dynamics",
            "Develop a causal inference framework for evaluating the wage returns of online education interventions",
            "Create a financial systemic risk monitor using network analysis of bilateral interbank exposure data",
            "Build a reinforcement learning agent for optimal execution of large block trades with market impact",
            "Develop an econometric model for nowcasting GDP growth using high-frequency satellite and payment data",
            "Create a structural demand estimation system for quantifying consumer welfare from digital platform mergers",
        ],
    },
    "Mathematics": {
        "skills": [
            "Python, numerical analysis, convex optimization, CVXPY, scipy.optimize, interior point methods, ADMM",
            "MATLAB, PDEs, finite element method, FEniCS, spectral methods, adaptive mesh refinement, multigrid",
            "Python, graph theory, network algorithms, integer programming, Gurobi, column generation, branch-and-bound",
            "Python, R, probabilistic graphical models, variational inference, normalizing flows, Bayesian deep learning",
            "Julia, scientific computing, automatic differentiation, stiff ODEs, DifferentialEquations.jl, sensitivity analysis",
            "Python, algebraic geometry, topology, persistent homology, Gudhi, TDA, simplicial complexes, Mapper",
        ],
        "intents": [
            "Develop efficient first-order algorithms for large-scale semidefinite programming in machine learning",
            "Build a neural ODE framework for learning continuous-time dynamics of irregular time series data",
            "Create a distributed optimization framework for federated learning with provable convergence guarantees",
            "Develop sample-efficient algorithms for online learning in adversarial and non-stationary environments",
            "Build a topological data analysis toolkit for detecting geometric structure in high-dimensional omics data",
            "Create a randomized numerical linear algebra library for large-scale eigenvalue and SVD computation",
        ],
    },
    "Chemistry": {
        "skills": [
            "Python, RDKit, molecular dynamics, AMBER, GROMACS, DFT, Gaussian, computational chemistry, force fields",
            "Organic synthesis, NMR spectroscopy, mass spectrometry, HPLC, flash chromatography, reaction optimization",
            "Python, machine learning, drug discovery, QSAR, virtual screening, generative molecular design, scaffold hopping",
            "Materials synthesis, XRD, SEM, TEM, XPS, electrochemistry, cyclic voltammetry, battery characterization",
            "Python, reaction informatics, USPTO dataset, template extraction, reaction prediction, retrosynthesis, SMILES",
        ],
        "intents": [
            "Build a graph neural network generative model for de novo design of kinase inhibitor drug candidates",
            "Develop a machine learning pipeline for predicting solid-state electrolyte ionic conductivity from structure",
            "Create an automated computer-aided synthesis planning tool with retrosynthetic route ranking and feasibility scoring",
            "Build a multi-task molecular property predictor for ADMET optimization to accelerate lead compound progression",
            "Develop a reaction condition recommendation system trained on large-scale chemical reaction databases",
        ],
    },
    "Civil Engineering": {
        "skills": [
            "AutoCAD, SAP2000, ETABS, structural analysis, reinforced concrete design, AISC steel design, seismic detailing",
            "ArcGIS, QGIS, Python, spatial analysis, urban mobility modeling, SUMO, traffic microsimulation, agent-based",
            "HEC-HMS, SWMM, HEC-RAS, hydrology, stormwater management, water quality modeling, LID design",
            "Revit, Navisworks, BIM coordination, Primavera P6, construction scheduling, cost estimation, lean construction",
            "Python, structural health monitoring, IoT sensors, vibration-based damage detection, digital twin modeling",
        ],
        "intents": [
            "Develop a structural health monitoring system using distributed MEMS sensors and ML for bridge damage detection",
            "Build an adaptive traffic signal control system using deep reinforcement learning for urban intersection networks",
            "Create a 100-year flood risk prediction model coupling hydrological simulation with downscaled climate projections",
            "Develop a BIM-integrated construction project management platform with automated schedule crash analysis",
            "Build a digital twin framework for real-time structural performance monitoring of long-span suspension bridges",
        ],
    },
    "Neuroscience": {
        "skills": [
            "Python, MNE, spike sorting, Kilosort, calcium imaging, two-photon microscopy, optogenetics, patch clamp",
            "MATLAB, SPM, FSL, fMRI preprocessing, functional connectivity, DCM, ICA, multivariate pattern analysis",
            "Python, deep learning, neural population decoding, BCI signal processing, LFP spectral analysis, CSD",
            "R, Python, statistical neuroscience, GLMs, point process models, dimensionality reduction, UMAP, t-SNE",
            "Python, connectomics, electron microscopy segmentation, synapse detection, graph analysis of neural circuits",
        ],
        "intents": [
            "Build a neural population decoder translating motor cortex ensemble activity into high-DoF prosthetic control",
            "Develop a real-time cognitive load estimator from EEG using compact transformer models for neuroergonomics",
            "Create a connectome analysis pipeline for identifying circuit-level structural changes in neurodegeneration",
            "Build an automated polysomnography staging system using transformer models with interpretable attention maps",
            "Develop a closed-loop neurostimulation controller for adaptive DBS therapy in Parkinson's disease",
        ],
    },
    "Environmental Science": {
        "skills": [
            "Python, Google Earth Engine, multispectral imagery, land cover classification, change detection, NDVI, SAR",
            "R, MaxEnt, species distribution modeling, ecological niche theory, biodiversity informatics, GBIF",
            "Python, xarray, NetCDF, climate model analysis, CMIP6, downscaling, bias correction, WRF",
            "ArcGIS, QGIS, spatial statistics, ecosystem services valuation, carbon accounting, InVEST model",
            "Python, air quality modeling, CMAQ, satellite retrieval, PM2.5 estimation, TROPOMI, AOD correction",
        ],
        "intents": [
            "Develop a deep learning deforestation monitor using weekly Sentinel-2 imagery with near-real-time alerting",
            "Build a global species range shift prediction model combining climate projections with trait-based dispersal",
            "Create a real-time air quality forecast system fusing satellite retrievals with ground monitors via ML",
            "Develop an above-ground biomass estimation model for tropical forests combining LiDAR and optical data",
            "Build a compound extreme event attribution framework using large-ensemble climate model simulations",
        ],
    },
}

SKILL_EXTRAS = [
    ", strong communication and technical writing",
    ", experience with cloud platforms (AWS/GCP/Azure)",
    ", containerization with Docker and Kubernetes",
    ", agile development and test-driven development",
    ", open source contributions and code review",
    ", experience with high-performance computing clusters",
    ", interdisciplinary research background",
    ", industry internship and production system experience",
    ", reproducible research and scientific computing practices",
    ", experience mentoring junior developers",
]

INTENT_EXTRAS = [
    " with a focus on real-world deployment and production scalability",
    " targeting measurable social impact in underserved communities",
    " with strong emphasis on interpretability, fairness, and transparency",
    " using exclusively open datasets and fully reproducible methods",
    " as part of a larger interdisciplinary collaborative research initiative",
    " with potential for commercialization and IP protection",
    " specifically optimized for resource-constrained and edge environments",
    " leveraging the latest advances in foundation models and LLMs",
    " backed by rigorous theoretical foundations and formal proofs",
    " combining novel hardware innovations with software co-design",
]

FIRST_NAMES = [
    "Alex", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Quinn", "Avery", "Reese", "Drew",
    "Sam", "Jamie", "Pat", "Chris", "Robin", "Lee", "Blake", "Cameron", "Dana", "Elliot",
    "Priya", "Arjun", "Wei", "Mei", "Yuki", "Kenji", "Amara", "Kofi", "Elena", "Ivan",
    "Sofia", "Mateo", "Aisha", "Omar", "Fatima", "Ravi", "Ananya", "Zara", "Lena", "Marco",
    "Nadia", "Felix", "Ingrid", "Dmitri", "Yara", "Hassan", "Soren", "Ingrid", "Tomas", "Vera",
    "Lucas", "Emma", "Noah", "Olivia", "Liam", "Ava", "Ethan", "Isabella", "James", "Mia",
]

LAST_NAMES = [
    "Chen", "Kim", "Patel", "Garcia", "Smith", "Johnson", "Williams", "Brown", "Davis", "Wilson",
    "Martinez", "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson",
    "Nguyen", "Lee", "Perez", "Robinson", "Clark", "Lewis", "Walker", "Hall", "Allen", "Young",
    "Hernandez", "King", "Wright", "Scott", "Torres", "Moore", "Hill", "Adams", "Baker", "Nelson",
    "Carter", "Mitchell", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards",
    "Collins", "Stewart", "Sanchez", "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy",
]


def check_ml_service():
    try:
        resp = requests.get(f"{ML_SERVICE_URL}/health", timeout=5)
        data = resp.json()
        if not data.get("model_loaded"):
            raise RuntimeError("ML service model not loaded yet")
        print(f"ML service ready at {ML_SERVICE_URL}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot reach ML service at {ML_SERVICE_URL}. "
            "Make sure Docker is running: docker compose up ml-service"
        )


def generate_profile_texts(n: int) -> list[dict]:
    dept_names = list(DEPARTMENTS.keys())
    profiles = []

    for _ in range(n):
        dept = random.choice(dept_names)
        templates = DEPARTMENTS[dept]

        skills = random.choice(templates["skills"])
        if random.random() < 0.4:
            skills += random.choice(SKILL_EXTRAS)

        intent = random.choice(templates["intents"])
        if random.random() < 0.4:
            intent += random.choice(INTENT_EXTRAS)

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        email = f"{name.lower().replace(' ', '.')}.{random.randint(100,999)}@university.edu"

        profiles.append({
            "user_id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "department": dept,
            "skills_text": skills,
            "intent_text": intent,
        })

    return profiles


def embed_batch(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        f"{ML_SERVICE_URL}/batch_embed",
        json={"texts": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def generate_dataset(n: int, output_path: Path) -> pd.DataFrame:
    print(f"\nGenerating {n:,} synthetic profiles...")
    profiles = generate_profile_texts(n)

    skills_texts = [p["skills_text"] for p in profiles]
    intent_texts = [p["intent_text"] for p in profiles]

    print(f"Generating skill embeddings in batches of {BATCH_SIZE}...")
    skill_embeddings = []
    for i in tqdm(range(0, n, BATCH_SIZE), desc="Skill embeddings"):
        batch = skills_texts[i : i + BATCH_SIZE]
        skill_embeddings.extend(embed_batch(batch))

    print(f"Generating intent embeddings in batches of {BATCH_SIZE}...")
    intent_embeddings = []
    for i in tqdm(range(0, n, BATCH_SIZE), desc="Intent embeddings"):
        batch = intent_texts[i : i + BATCH_SIZE]
        intent_embeddings.extend(embed_batch(batch))

    for i, p in enumerate(profiles):
        p["skill_embedding"] = skill_embeddings[i]
        p["intent_embedding"] = intent_embeddings[i]

    df = pd.DataFrame(profiles)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"Saved {n:,} profiles → {output_path}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic student profiles with real embeddings")
    parser.add_argument("--scale", choices=["1k", "10k", "all"], default="1k",
                        help="Dataset size to generate (default: 1k)")
    parser.add_argument("--ml-url", default=None, help="Override ML service URL")
    args = parser.parse_args()

    global ML_SERVICE_URL
    if args.ml_url:
        ML_SERVICE_URL = args.ml_url

    check_ml_service()

    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    scales = {"1k": 1000, "10k": 10000}

    if args.scale == "all":
        to_generate = list(scales.items())
    else:
        to_generate = [(args.scale, scales[args.scale])]

    for label, n in to_generate:
        path = output_dir / f"synthetic_{label}.parquet"
        if path.exists():
            print(f"\n{path} already exists — skipping. Delete it to regenerate.")
            continue
        generate_dataset(n, path)

    print("\nDone. Datasets ready for benchmarking.")


if __name__ == "__main__":
    main()
