"""
Seeds the PGVector knowledge base with Mayo Clinic medical reference content.

Run once after starting Docker:
    python scripts/seed_knowledge.py

This populates the "mayo_medical_knowledge" collection used by the accuracy agent.
Topics: diabetes, hypertension, heart disease, cancer screening, mental health,
        COVID-19, Mayo editorial standards.
"""

import sys
import os

# Allow running from scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config.settings import settings

KNOWLEDGE_BASE = [
    # ------------------------------------------------------------------ Diabetes
    {
        "content": """
Diabetes mellitus is a group of metabolic diseases characterized by high blood sugar levels
over a prolonged period. Type 1 diabetes results from the pancreas's failure to produce enough
insulin due to loss of beta cells. Type 2 diabetes begins with insulin resistance, where cells
fail to respond to insulin properly. Symptoms of high blood sugar include frequent urination,
increased thirst, and increased hunger. If left untreated, diabetes can cause many complications
including cardiovascular disease, chronic kidney disease, stroke, diabetic retinopathy leading
to blindness, and poor blood flow in the limbs leading to amputations.

Type 2 diabetes is largely preventable. Risk factors include being overweight, physical
inactivity, family history, age over 45, history of gestational diabetes, prediabetes,
high blood pressure, and abnormal cholesterol or triglyceride levels.

Blood sugar control is central to diabetes management. A1C test measures average blood sugar
over two to three months. Target A1C for most people with diabetes is below 7%. Normal A1C
is below 5.7%; prediabetes is 5.7% to 6.4%; diabetes is 6.5% or higher.
        """,
        "metadata": {"topic": "diabetes", "source": "mayo_clinic"},
    },
    {
        "content": """
Diabetes treatment depends on type. Type 1 diabetes requires insulin therapy — multiple
daily injections or an insulin pump. Type 2 diabetes treatment starts with lifestyle changes:
healthy eating, regular exercise (at least 150 minutes of moderate aerobic activity per week),
and weight loss. Medications include metformin (first-line), SGLT2 inhibitors, GLP-1 receptor
agonists, DPP-4 inhibitors, sulfonylureas, and insulin when needed.

Monitoring blood sugar regularly is essential. People with Type 1 should check multiple times
daily. Continuous glucose monitors (CGMs) can provide real-time readings. Hypoglycemia
(blood sugar below 70 mg/dL) symptoms include shakiness, sweating, confusion, and can be
life-threatening. Treat with 15g of fast-acting carbohydrates (glucose tablets, juice).

Diabetes complications can be delayed or prevented with good blood sugar, blood pressure,
and cholesterol control. Annual foot exams, eye exams, and kidney function tests (eGFR,
urine albumin) are recommended for people with diabetes.
        """,
        "metadata": {"topic": "diabetes", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ Hypertension
    {
        "content": """
High blood pressure (hypertension) is a common condition where the long-term force of blood
against artery walls is high enough to cause health problems like heart disease. Blood pressure
is measured in millimeters of mercury (mmHg). Normal blood pressure is below 120/80 mmHg.
Elevated: 120-129 systolic and below 80 diastolic. Stage 1 hypertension: 130-139/80-89.
Stage 2: 140+ systolic or 90+ diastolic. Hypertensive crisis: above 180/120.

Most people with high blood pressure have no symptoms, even if readings are dangerously high.
A few people with high blood pressure may have headaches, shortness of breath, or nosebleeds.
These symptoms aren't specific and usually don't occur until blood pressure has reached a
severe or life-threatening stage.

Risk factors include age (risk increases with age), race (more common in Black adults),
family history, overweight or obesity, physical inactivity, tobacco use, too much sodium,
low potassium, excessive alcohol, stress, and certain chronic conditions.
        """,
        "metadata": {"topic": "hypertension", "source": "mayo_clinic"},
    },
    {
        "content": """
Hypertension treatment: Lifestyle changes are the first step — healthy diet (DASH diet:
rich in fruits, vegetables, whole grains, low-fat dairy, lean proteins; low in saturated fat
and sodium), regular exercise, maintaining healthy weight, limiting alcohol, quitting smoking,
managing stress.

Medications: ACE inhibitors (lisinopril, enalapril), ARBs (losartan, valsartan), calcium
channel blockers (amlodipine, diltiazem), diuretics (hydrochlorothiazide, chlorthalidone),
beta-blockers (metoprolol, atenolol). Most people need more than one medication to control
blood pressure. Home monitoring is encouraged — take readings at the same time each day,
rest 5 minutes before measuring, take two readings 1 minute apart.
        """,
        "metadata": {"topic": "hypertension", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ Heart Disease
    {
        "content": """
Coronary artery disease (CAD) is the most common type of heart disease. It develops when the
major blood vessels that supply the heart with blood, oxygen and nutrients (coronary arteries)
become damaged or diseased. Cholesterol-containing deposits (plaque) in the arteries and
inflammation are usually to blame for coronary artery disease.

Symptoms: Chest pain (angina) — pressure, tightness, burning, or aching in the chest, usually
on the left side; shortness of breath; heart attack symptoms include crushing chest pressure,
sweating, nausea, upper arm or jaw pain. Women may experience atypical symptoms including
fatigue, nausea, and back or jaw pain.

Risk factors: Age, sex (men at higher risk; women's risk increases after menopause), family
history, smoking, high blood pressure, high cholesterol, diabetes, overweight or obesity,
physical inactivity, high stress, unhealthy diet, excessive alcohol.

Heart attack: Complete blockage of a coronary artery. Treatment within 90 minutes (door-to-balloon
time) is critical. Treatments: thrombolytics, PCI (percutaneous coronary intervention/stenting),
CABG (coronary artery bypass grafting surgery).
        """,
        "metadata": {"topic": "heart_disease", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ Cancer Screening
    {
        "content": """
Cancer screening guidelines from Mayo Clinic:

Breast cancer: Mammography recommended annually starting at 40 for women at average risk.
Women at high risk (BRCA mutation, strong family history) may need earlier screening and MRI.

Colorectal cancer: Screening starting at age 45 for average-risk adults. Options include
colonoscopy every 10 years, annual fecal immunochemical test (FIT), stool DNA test every
1-3 years, CT colonography every 5 years. Earlier screening for family history of colon cancer.

Lung cancer: Annual low-dose CT scan for adults 50-80 with 20+ pack-year smoking history
who currently smoke or quit within past 15 years.

Prostate cancer: PSA test discussion starting at 50 for average risk, 40-45 for high risk.
Shared decision-making recommended.

Cervical cancer: Pap smear every 3 years for ages 21-29; Pap + HPV co-test every 5 years
for ages 30-65. HPV vaccination recommended through age 26.

Skin cancer: Annual skin exam by dermatologist recommended, especially for those with
numerous moles, fair skin, or history of sun exposure.
        """,
        "metadata": {"topic": "cancer_screening", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ Mental Health
    {
        "content": """
Depression (major depressive disorder) is a common and serious medical illness that negatively
affects how you feel, the way you think, and how you act. Symptoms: persistent sad, anxious,
or empty mood; loss of interest or pleasure in activities; changes in appetite; sleep problems;
loss of energy; difficulty thinking or concentrating; thoughts of death or suicide.

Diagnosis: DSM-5 criteria — 5 or more symptoms for at least 2 weeks, including depressed mood
or loss of interest. PHQ-9 is a validated screening tool.

Treatment: Psychotherapy (CBT is most evidence-based), medication (SSRIs: fluoxetine,
sertraline, escitalopram; SNRIs: venlafaxine, duloxetine), or combination. Most people respond
within 4-8 weeks. Medication should be continued 6-12 months after remission to prevent relapse.
For severe or treatment-resistant depression: TMS, ECT, ketamine/esketamine (Spravato).

Anxiety disorders: GAD, panic disorder, social anxiety disorder. Treatment: CBT, SSRIs/SNRIs,
buspirone for GAD. Benzodiazepines for short-term relief only — avoid long-term use due to
dependence risk.

Suicide prevention: If in crisis, contact 988 Suicide and Crisis Lifeline (call or text 988).
        """,
        "metadata": {"topic": "mental_health", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ Mayo Editorial Standards
    {
        "content": """
Mayo Clinic editorial standards for health content:

Reading level: Content should target 6th to 8th grade reading level (Flesch-Kincaid Grade
Level 6-8). Flesch Reading Ease score should be 60-70 (plain English).

Attribution: All articles must be attributed to "Mayo Clinic Staff" or a named reviewer
with credentials. The review date must appear on the page.

Review cycle: Content must be reviewed and updated at least every 2 years. Outdated content
(last reviewed more than 24 months ago) should be flagged for immediate review.

Prohibited language:
- Absolute claims: "cures," "eliminates," "guarantees"
- Unsubstantiated superlatives: "the best," "the only," "revolutionary"
- Off-label promotion without appropriate caveats
- Patient-identifiable information without consent

Required elements:
- H1 heading matching the page topic
- Meta description 150-160 characters
- JSON-LD structured data (MedicalWebPage or WebPage schema)
- Canonical URL matching the published URL
- At minimum: overview, symptoms, causes sections for condition pages
- Internal links to related Mayo Clinic content
- "Consult your doctor" or similar hedging for all treatment recommendations

Taxonomy: Condition pages must be categorized under the correct ICD-10 chapter.
Pages must include accurate medical taxonomy tags.
        """,
        "metadata": {"topic": "mayo_editorial_standards", "source": "mayo_clinic"},
    },
    # ------------------------------------------------------------------ COVID-19
    {
        "content": """
COVID-19 (coronavirus disease 2019) is caused by SARS-CoV-2. Symptoms range from mild
(fever, cough, fatigue, loss of taste/smell) to severe (difficulty breathing, chest pain,
confusion). Long COVID: symptoms persisting 4+ weeks after infection, including fatigue,
brain fog, shortness of breath, post-exertional malaise.

Vaccines: mRNA vaccines (Pfizer-BioNTech, Moderna) and protein subunit (Novavax) are highly
effective at preventing severe disease, hospitalization, and death. Updated (XBB.1.5 or JN.1)
boosters recommended annually for adults, particularly those 65+ and immunocompromised.

Treatment: Paxlovid (nirmatrelvir/ritonavir) — antivirals for high-risk adults within 5 days
of symptom onset. Remdesivir for hospitalized patients. Monoclonal antibodies have limited
efficacy against current variants.

Prevention: Vaccination, ventilation, masking in high-risk settings, hand hygiene,
staying home when sick.

Transmission: Primarily airborne — respiratory droplets and aerosols. Risk highest in
crowded, poorly ventilated indoor spaces.
        """,
        "metadata": {"topic": "covid19", "source": "mayo_clinic"},
    },
]


def seed_knowledge_base() -> None:
    print("Seeding Mayo Clinic medical knowledge base...")
    print(f"Connection: {settings.PGVECTOR_CONNECTION_STRING}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " "],
    )

    docs = []
    for entry in KNOWLEDGE_BASE:
        chunks = splitter.create_documents(
            texts=[entry["content"].strip()],
            metadatas=[entry["metadata"]],
        )
        docs.extend(chunks)

    print(f"Created {len(docs)} chunks from {len(KNOWLEDGE_BASE)} knowledge base entries")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY,
    )

    print("Uploading to PGVector (this may take ~30 seconds)...")
    PGVector.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="mayo_medical_knowledge",
        connection=settings.PGVECTOR_CONNECTION_STRING,
        use_jsonb=True,
        pre_delete_collection=True,  # Wipe and re-seed on each run
    )

    print(f"Done! Seeded {len(docs)} chunks into 'mayo_medical_knowledge' collection.")


if __name__ == "__main__":
    seed_knowledge_base()
