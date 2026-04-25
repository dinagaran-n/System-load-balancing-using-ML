print("Starting ML training...")

import mysql.connector
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="d1i2n3a4",
    database="load_balancer"
)

print("Connected to database")

query = "SELECT cpu, memory, processes, load_level FROM system_metrics"
df = pd.read_sql(query, conn)
conn.close()

print("Data loaded")

df['load_level'] = df['load_level'].map({
    'LOW': 0,
    'MEDIUM': 1,
    'HIGH': 2
})

X = df[['cpu', 'memory', 'processes']]
y = df['load_level']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = DecisionTreeClassifier()
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Model trained successfully")
print("Accuracy:", accuracy)
