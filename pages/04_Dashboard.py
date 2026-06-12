"""Dashboard page — Bolão Copa FIFA 2k26."""

import streamlit as st
import database as db
import scoring

st.set_page_config(page_title="Dashboard — Bolão 2k26", layout="wide")

db.init_db()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal.")
    st.stop()

st.title("📊 Dashboard")
st.markdown("Destaques e estatísticas do bolão.")

metrics = scoring.dashboard_metrics()

# Se o dicionário vier completamente vazio por falta de usuários ativos
if not metrics:
    st.info("Dashboard disponível após cadastro de participantes e palpites.")
    st.stop()

leader = metrics.get("leader")
best_phase = metrics.get("best_phase", {"phase": None, "user": None, "points": -1})
exact_king = metrics.get("exact_king")
hat_trick = metrics.get("hat_trick")
climb = metrics.get("biggest_climb", {"user": None, "delta": 0})
zebra = metrics.get("zebra_king")

# --- LINHA SUPERIOR ---
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 👑 Líder Geral")
    if leader:
        st.metric(
            label=leader.full_name,
            value=f"{leader.total_points} pts",
            delta=f"{leader.exact_scores} placares exatos",
        )
    else:
        st.info("Nenhum dado computado.")

with c2:
    st.markdown("### 🏅 Melhor da Fase")
    if best_phase and best_phase.get("phase"):
        st.metric(
            label=best_phase["user"] or "-",
            value=f"{best_phase['points']} pts" if best_phase["points"] >= 0 else "-",
            delta=best_phase["phase"],
        )
    else:
        st.info("Sem dados de fases concluídas.")

with c3:
    st.markdown("### 🎯 Rei do Placar Exato")
    if exact_king:
        st.metric(
            label=exact_king.full_name,
            value=f"{exact_king.exact_scores} exatos",
            delta=f"{exact_king.total_points} pts totais",
        )
    else:
        st.info("Nenhum placar exato ainda.")

st.divider()

# --- LINHA INFERIOR ---
c4, c5, c6 = st.columns(3)

with c4:
    st.markdown("### ⚡ Hat-Trick")
    st.caption("Mais sequências de 3+ placares exatos consecutivos")
    if hat_trick and hat_trick.get("full_name"):
        st.metric(
            label=hat_trick["full_name"],
            value=f"{hat_trick['hat_tricks']} hat-tricks",
            delta=f"Maior sequência: {hat_trick['max_streak']}",
        )
    else:
        st.info("Nenhum hat-trick (3 exatos seguidos) registrado ainda.")

with c5:
    st.markdown("### 📈 Maior Escalada")
    st.caption("Maior subida no ranking (snapshots)")
    if climb and climb.get("user") and climb.get("delta", 0) > 0:
        st.metric(
            label=climb["user"],
            value=f"+{climb['delta']} posições",
        )
    else:
        st.info("Aguardando novas rodadas para computar variações de posições.")

with c6:
    st.markdown("### 🦓 Rei das Zebras")
    st.caption("Mais pontos em acertos de resultados surpresa")
    if zebra and zebra.get("full_name"):
        st.metric(
            label=zebra["full_name"],
            value=f"{zebra['zebra_points']} pts",
            delta=f"{zebra['zebra_count']} zebras",
        )
    else:
        st.info("Nenhuma zebra estatística detectada nos jogos finalizados.")

st.divider()

st.subheader("Visão geral do ranking")
df = scoring.ranking_dataframe()
if not df.empty:
    top5 = df.head(5)
    st.dataframe(top5, use_container_width=True, hide_index=True)

    st.subheader("Distribuição de pontos")
    chart_data = df.set_index("Participante")["Pontos Totais"]
    st.bar_chart(chart_data)

st.divider()
st.subheader("Status das fases")
phases = db.list_phases()
for phase in phases:
    status = phase["status"]
    icon = {"Não iniciada": "⬜", "Aberta": "🟢", "Fechada": "🟡", "Finalizada": "✅"}.get(status, "❓")
    st.markdown(f"{icon} **{phase['name']}** — {status}")
