output "instance_id" {
  description = "EC2 instance ID for SSM Session Manager access."
  value       = aws_instance.monitored_host.id
}

output "public_ip" {
  description = "Public IP to add to the Prometheus scrape target."
  value       = aws_instance.monitored_host.public_ip
}

output "node_exporter_target" {
  description = "Prometheus node_exporter target."
  value       = "${aws_instance.monitored_host.public_ip}:9100"
}

