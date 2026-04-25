# 🚀 Predictive System Load Balancing

### Using OS Metrics, ML Models, DBMS, and Algorithms

---

## 📌 Overview

This project is a **Predictive System Load Monitoring and Balancing System** that collects real-time operating system metrics and uses a **machine learning model** to predict system load conditions.

It supports a scalable architecture where devices can send their metrics to a centralized backend, enabling intelligent monitoring and decision-making through a web dashboard.

---

## 🎯 Features

* 📊 Real-time CPU, Memory, and Process monitoring
* 🤖 Machine Learning-based load prediction (LOW / MEDIUM / HIGH)
* 🌐 REST API using Flask
* 🗄 MySQL (Railway) database integration
* 💻 Web dashboard with dynamic charts
* 🔌 Agent-based system for extensibility (multi-device ready)
* ☁️ Cloud deployment (Render compatible)

---

## 🧠 System Architecture

```
Device (Metrics Agent)
        ↓
Flask Backend API
        ↓
MySQL Database (Railway)
        ↓
Machine Learning Model
        ↓
Frontend Dashboard
```

---

## ⚙️ Tech Stack

* **Backend:** Python, Flask
* **Frontend:** HTML, CSS, JavaScript, Chart.js
* **Database:** MySQL (Railway)
* **ML Model:** Scikit-learn
* **System Metrics:** psutil
* **Deployment:** Render

---

## 📁 Project Structure

```
Sem4_Project/
│
├── backend/
│   ├── api/
│   │   └── api.py
│   ├── ml/
│   │   └── load_predictor.pkl
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── charts.js
│
├── metrics_agent.py
├── requirements.txt
└── README.md
```

---

## 🔧 Setup Instructions

### 1️⃣ Clone the Repository

```
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

---

### 2️⃣ Install Dependencies

```
pip install -r requirements.txt
```

---

### 3️⃣ Configure Environment Variables

#### Windows (PowerShell)

```
$env:DB_HOST="your_host"
$env:DB_USER="root"
$env:DB_PASSWORD="your_password"
$env:DB_NAME="railway"
$env:DB_PORT="50531"
```

#### Mac/Linux

```
export DB_HOST=your_host
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=railway
export DB_PORT=50531
```

---

### 4️⃣ Run Backend

```
python backend/api/api.py
```

---

### 5️⃣ Run Metrics Agent

```
python metrics_agent.py
```


## 📡 API Endpoints

| Endpoint               | Method | Description            |
| ---------------------- | ------ | ---------------------- |
| `/register-metrics`    | POST   | Receive system metrics |
| `/devices`             | GET    | Get active devices     |
| `/device-metrics/<id>` | GET    | Get metrics for device |
| `/predicted-load/<id>` | GET    | Get prediction         |

---

## 🤖 Machine Learning

* Model: Classification model (Random Forest / similar)
* Input: CPU, Memory, Processes
* Output: Load category (LOW / MEDIUM / HIGH)

---

## 📊 Dashboard

* Real-time metrics visualization
* Load prediction display
* Dynamic charts using Chart.js

---

## 🚀 Deployment

* Backend: Deploy on **Render**
* Database: Use **Railway MySQL**
* Frontend: Served via Flask or static hosting

---

## 🔮 Future Improvements

* 🔔 Alert system (email/SMS)
* ⚖️ Automatic load balancing
* 📱 Mobile app support
* 🧠 Advanced ML models
* ☸️ Kubernetes integration

---

## 👨‍💻 Author

**Dinagaran N**

---

## 📜 License

This project is for academic and educational purposes.
