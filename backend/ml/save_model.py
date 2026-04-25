import mysql.connector
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import joblib

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="d1i2n3a4",
    database="load_balancer"
)

query = "SELECT cpu, memory, processes, load_level FROM system_metrics"
df = pd.read_sql(query, conn)
conn.close()

df['load_level'] = df['load_level'].map({
    'LOW': 0,
    'MEDIUM': 1,
    'HIGH': 2
})

X = df[['cpu', 'memory', 'processes']]
y = df['load_level']

model = DecisionTreeClassifier()
model.fit(X, y)

joblib.dump(model, "load_predictor.pkl")

print("ML model saved successfully")
