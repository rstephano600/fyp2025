
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

print("🚀 Starting Training Script...")

# Step 1: Load dataset
if not os.path.exists("sms_parser/real_sms_dataset.csv"):
    print("❌ Dataset not found.")
    exit()

df = pd.read_csv("sms_parser/real_sms_dataset.csv")

if df.empty:
    print("❌ Dataset is empty.")
    exit()

print(f"✅ Loaded {len(df)} messages.")

# Step 2: Build training pipeline
model = Pipeline([
    ('tfidf', TfidfVectorizer(lowercase=True, stop_words='english')),
    ('clf', MultinomialNB())
])

# Step 3: Split & Train
X_train, X_test, y_train, y_test = train_test_split(df['text'], df['label'], test_size=0.2, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

# Step 4: Show metrics
print("\n📊 Classification Report:")
print(classification_report(y_test, y_pred))

# Step 5: Save model
joblib.dump(model, "sms_parser/sms_model.pkl")
print("✅ Model trained and saved as 'sms_model.pkl'")
