# Kapsul-Portal  
Web + Mobile Dashboard for the **Kapsul Real-Time Smart Medicine Dispenser**

## 🌐 Overview  
Kapsul-Portal is the Flask-based dashboard and backend that connects to the Kapsul dispenser.  
It handles schedules, medicine data, user management, real-time logs, and WebSocket communication with the device.

The portal is designed to work seamlessly on both **web** and **mobile**, with deployment on **HuggingFace Spaces**.

---

## ✨ Features  
- Upload and manage medicine schedules  
- Real-time WebSocket communication with ESP32  
- Logs of dispensed, missed, or upcoming doses  
- Mobile + web responsive UI  
- User & caregiver modes  
- Live status monitoring  
- Cloud-synced notifications  
- Automatic syncing with Kapsul-PlatformIo  

---

## 🧰 Tech Stack  
- **Python**  
- **Flask**  
- **Jinja Templates**  
- **WebSockets (Flask-SocketIO)**  
- **HTML/CSS/Bootstrap**  
- **JavaScript**  
- **HuggingFace Deployment**  

---

## 🧠 What the Portal Does  
- Stores medicine schedules  
- Sends commands to the hardware  
- Displays live logs of medicines dispensed  
- Generates alerts for missed doses  
- Allows full configuration of the dispenser  
- Provides a simple UI for users & caregivers  

---

## 📱 Mobile + Web Dashboard  
The dashboard is fully responsive and supports:  
- Add/remove medicines  
- Set time slots  
- Track adherence  
- Manual override commands  
- Live dispenser status  

---

## 🛠 Tools Used  
- VS Code  
- GitHub  
- HuggingFace Spaces  
- Flask ecosystem  
- WebSocket utilities  
- Documentation, YouTube tutorials  
- ChatGPT  

---

## 🔧 How to Run (Local)  
1. Install dependencies:  
   ```bash
   pip install -r requirements.txt
