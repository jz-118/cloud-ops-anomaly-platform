{{- define "cloud-ops.name" -}}
cloud-ops
{{- end }}

{{- define "cloud-ops.labels" -}}
app.kubernetes.io/part-of: cloud-ops-platform
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

