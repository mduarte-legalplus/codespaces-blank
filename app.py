import io
import json
import re
from dataclasses import dataclass
from typing import List

import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="AI Contract Review (ES)", page_icon="🧠", layout="wide")


@dataclass
class ReviewRule:
    name: str
    description: str
    trigger_patterns: List[str]
    severity: str
    expected_standard: str
    draft_fix: str


DEFAULT_RULES = [
    {
        "name": "Limitación de responsabilidad desbalanceada",
        "description": "Detecta cláusulas que excluyen toda responsabilidad del proveedor o no incluyen tope razonable.",
        "trigger_patterns": [
            r"sin\s+ninguna\s+responsabilidad",
            r"en\s+ning[úu]n\s+caso\s+ser[áa].{0,40}responsable",
            r"renuncia\s+total\s+a\s+reclamar",
        ],
        "severity": "Alta",
        "expected_standard": "En contratos tecnológicos B2B se suele acordar un tope de responsabilidad (ej. 12 meses de fees), con carve-outs para dolo, fraude, confidencialidad y protección de datos.",
        "draft_fix": "Sugerencia: 'La responsabilidad total acumulada de cada Parte derivada del Contrato no excederá el equivalente a los importes pagados en los 12 meses previos al hecho generador, salvo en casos de dolo, fraude, incumplimiento de confidencialidad o normativa de protección de datos.'",
    },
    {
        "name": "Protección de datos incompleta",
        "description": "Identifica ausencia de obligaciones concretas sobre tratamiento de datos personales.",
        "trigger_patterns": [
            r"datos\s+personales",
            r"rgpd|gdpr",
            r"encargado\s+del\s+tratamiento",
        ],
        "severity": "Alta",
        "expected_standard": "Debe incluir base legal, roles (responsable/encargado), medidas técnicas y organizativas, notificación de brechas, subencargados y transferencias internacionales.",
        "draft_fix": "Sugerencia: incorporar un Anexo de Tratamiento de Datos (DPA) con obligaciones de seguridad, auditoría, subencargados, y notificación de brechas en ≤72 horas.",
    },
    {
        "name": "SLA y soporte no definidos",
        "description": "Busca contratos SaaS sin compromisos mínimos de disponibilidad y soporte.",
        "trigger_patterns": [
            r"soporte",
            r"nivel(es)?\s+de\s+servicio|sla",
            r"disponibilidad|uptime",
        ],
        "severity": "Media",
        "expected_standard": "Mercado SaaS: uptime 99.5%/99.9%, ventana de mantenimiento planificada, tiempos de respuesta por severidad y créditos por incumplimiento.",
        "draft_fix": "Sugerencia: incluir Anexo SLA con disponibilidad mensual, exclusiones, tiempos de respuesta/resolución y service credits.",
    },
    {
        "name": "Terminación sin transición",
        "description": "Revisa si se contempla salida ordenada y devolución de datos al término.",
        "trigger_patterns": [
            r"terminaci[óo]n|resoluci[óo]n",
            r"devoluci[óo]n\s+de\s+datos|portabilidad",
            r"asistencia\s+de\s+transici[óo]n",
        ],
        "severity": "Media",
        "expected_standard": "Es estándar definir periodo de extracción de datos, formato interoperable, y soporte de transición con coste predefinido.",
        "draft_fix": "Sugerencia: 'A la terminación, el Proveedor facilitará por 60 días la exportación de datos en formato interoperable y, previa tarifa acordada, asistencia de transición razonable.'",
    },
]

DEFAULT_PLAYBOOK = {
    "jurisdiction": "España",
    "contract_type": "SaaS / Licencia tecnológica",
    "risk_profile": "Balanced",
    "rules": DEFAULT_RULES,
}


def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    return "\n".join(text_parts)


def split_into_clauses(contract_text: str) -> List[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", contract_text) if block.strip()]
    return [block for block in blocks if len(block) > 80]


def build_rules_from_json(raw_json: str) -> List[ReviewRule]:
    payload = json.loads(raw_json)
    rules = payload.get("rules", []) if isinstance(payload, dict) else payload

    parsed_rules = []
    for rule in rules:
        parsed_rules.append(
            ReviewRule(
                name=rule.get("name", "Regla sin nombre"),
                description=rule.get("description", ""),
                trigger_patterns=rule.get("trigger_patterns", []),
                severity=rule.get("severity", "Media"),
                expected_standard=rule.get("expected_standard", ""),
                draft_fix=rule.get("draft_fix", ""),
            )
        )
    return parsed_rules


def analyze_contract(clauses: List[str], rules: List[ReviewRule]):
    findings = []
    for i, clause in enumerate(clauses, start=1):
        lowered = clause.lower()

        for rule in rules:
            hits = []
            for pattern in rule.trigger_patterns:
                if re.search(pattern, lowered, flags=re.IGNORECASE):
                    hits.append(pattern)

            # Mark risk when there are no hits for "required" clauses like DPA/SLA,
            # or when a problematic expression is explicitly found.
            if hits:
                findings.append(
                    {
                        "clause_number": i,
                        "rule": rule.name,
                        "severity": rule.severity,
                        "why_flagged": f"Coincidencias detectadas: {', '.join(hits)}",
                        "industry_standard": rule.expected_standard,
                        "draft_change": rule.draft_fix,
                        "excerpt": clause[:420] + ("..." if len(clause) > 420 else ""),
                    }
                )

    # Extra global checks for missing content
    full = "\n".join(clauses).lower()
    if "datos personales" not in full and "rgpd" not in full and "gdpr" not in full:
        findings.append(
            {
                "clause_number": "N/A",
                "rule": "Falta cláusula de protección de datos",
                "severity": "Alta",
                "why_flagged": "No se detectó sección de tratamiento de datos personales.",
                "industry_standard": "Incluir DPA con responsabilidades, medidas de seguridad y notificación de brechas.",
                "draft_change": "Añadir cláusula/anexo DPA alineado a RGPD (roles, subencargados, transferencias, brechas ≤72h).",
                "excerpt": "No aplica (alerta de ausencia).",
            }
        )

    if "sla" not in full and "nivel de servicio" not in full and "disponibilidad" not in full:
        findings.append(
            {
                "clause_number": "N/A",
                "rule": "Falta anexo SLA",
                "severity": "Media",
                "why_flagged": "No se detectó compromiso operativo de soporte/disponibilidad.",
                "industry_standard": "Definir uptime, exclusiones, soporte por severidad y créditos de servicio.",
                "draft_change": "Agregar anexo SLA con uptime mensual, tiempos de respuesta, resolución y service credits.",
                "excerpt": "No aplica (alerta de ausencia).",
            }
        )

    return findings


st.title("🧠 AI Contract Review para contratos tecnológicos (Español)")
st.caption("Carga un contrato + playbook de negociación para detectar alertas y generar propuestas de redacción.")

left, right = st.columns([1, 1])

with left:
    st.subheader("1) Contrato")
    input_type = st.radio("Formato de entrada", ["Pegar texto", "Subir PDF"])
    contract_text = ""

    if input_type == "Pegar texto":
        contract_text = st.text_area(
            "Texto del contrato",
            height=340,
            placeholder="Pega aquí el contrato en español...",
        )
    else:
        pdf_file = st.file_uploader("Sube contrato en PDF", type=["pdf"])
        if pdf_file:
            try:
                contract_text = extract_text_from_pdf(pdf_file)
                st.success("PDF procesado correctamente.")
            except Exception as exc:
                st.error(f"No se pudo leer el PDF: {exc}")

with right:
    st.subheader("2) Playbook y reglas")
    st.write("Puedes usar el playbook base o editarlo (JSON).")
    playbook_json = st.text_area(
        "Playbook (JSON)",
        value=json.dumps(DEFAULT_PLAYBOOK, indent=2, ensure_ascii=False),
        height=340,
    )

analyze = st.button("Analizar contrato", type="primary", use_container_width=True)

if analyze:
    if not contract_text.strip():
        st.warning("Primero agrega un contrato (texto o PDF).")
    else:
        try:
            rules = build_rules_from_json(playbook_json)
        except json.JSONDecodeError as exc:
            st.error(f"El JSON del playbook no es válido: {exc}")
            st.stop()

        clauses = split_into_clauses(contract_text)
        findings = analyze_contract(clauses, rules)

        st.subheader("3) Resultado del análisis")
        st.metric("Cláusulas analizadas", len(clauses))
        st.metric("Alertas detectadas", len(findings))

        if not findings:
            st.success("No se detectaron alertas con las reglas actuales.")
        else:
            severity_order = {"Alta": 0, "Media": 1, "Baja": 2}
            findings = sorted(findings, key=lambda f: severity_order.get(f["severity"], 3))

            csv_data = io.StringIO()
            headers = [
                "clause_number",
                "rule",
                "severity",
                "why_flagged",
                "industry_standard",
                "draft_change",
                "excerpt",
            ]
            csv_data.write(",".join(headers) + "\n")
            for row in findings:
                escaped = []
                for h in headers:
                    value = str(row[h]).replace('"', '""')
                    escaped.append(f'"{value}"')
                csv_data.write(",".join(escaped) + "\n")

            st.download_button(
                "⬇️ Descargar reporte CSV",
                data=csv_data.getvalue(),
                file_name="reporte_alertas_contrato.csv",
                mime="text/csv",
            )

            for finding in findings:
                with st.expander(
                    f"[{finding['severity']}] {finding['rule']} · Cláusula {finding['clause_number']}",
                    expanded=finding["severity"] == "Alta",
                ):
                    st.markdown(f"**Por qué se alertó:** {finding['why_flagged']}")
                    st.markdown(f"**Estándar de mercado:** {finding['industry_standard']}")
                    st.markdown(f"**Propuesta de redacción:** {finding['draft_change']}")
                    st.code(finding["excerpt"], language="markdown")

st.divider()
st.caption(
    "Nota: Este asistente es una primera capa de revisión. No sustituye la validación de abogados especializados ni el análisis contextual de cada negociación."
)
