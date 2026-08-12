# Kubernetes Monitoring Project

## Components
- Flask Application
- Docker
- Kubernetes (Minikube)
- Prometheus
- Grafana
- Loki
- Promtail
- Kubernetes Event Exporter


## Setup Steps

### 1. Start Minikube

minikube start


### 2. Build Flask Docker Image

docker build -t flask-app .


### 3. Deploy Flask Application

kubectl apply -f deployment.yaml
kubectl apply -f service.yaml


### 4. Install Prometheus and Grafana

helm install prometheus prometheus-community/kube-prometheus-stack


### 5. Install Loki

helm install loki grafana/loki -f loki-values.yaml


### 6. Install Promtail

helm install promtail grafana/promtail -f promtail-values.yaml


### 7. Install Kubernetes Event Exporter

helm install kubernetes-event-exporter \
bitnami/kubernetes-event-exporter \
-f event-values.yaml


### 8. Access Grafana

kubectl port-forward svc/prometheus-grafana 3000:80

Open:

http://localhost:3000


### 9. Loki Query Example

Use Loki datasource in Grafana:
{pod=~"kubernetes-event-exporter.*"}
