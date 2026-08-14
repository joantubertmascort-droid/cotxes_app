import streamlit as st
import random
from datetime import date
from supabase import create_client


# ============================================================
# CONFIGURACIÓ
# ============================================================

st.set_page_config(
    page_title="Cotxe de Festa",
    page_icon="🚗",
    layout="wide"
)

AMICS = [
    "Tubert",
    "Miralles",
    "Magaña",
    "Hector",
    "Adri",
    "Porsell",
    "Gugu",
    "Carbo",
    "Hicham",
    "Younes",
    "Pablo",
    "Biel",
    "Isma"
]

PUNTS_INICIALS = 100.0

# Com més gran sigui aquest número,
# més exagerada serà la diferència de probabilitats.
EXPONENT_RULETA = 2.0


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():

    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)


supabase = get_supabase()


# ============================================================
# CREAR ELS 13 AMICS AUTOMÀTICAMENT
# ============================================================

def ensure_friends():

    response = (
        supabase
        .table("friends")
        .select("id,name")
        .execute()
    )

    existing_names = {
        row["name"]
        for row in response.data
    }

    missing = [
        {"name": name}
        for name in AMICS
        if name not in existing_names
    ]

    if missing:
        supabase \
            .table("friends") \
            .insert(missing) \
            .execute()


ensure_friends()


# ============================================================
# OBTENIR AMICS
# ============================================================

def get_friends():

    response = (
        supabase
        .table("friends")
        .select("id,name")
        .execute()
    )

    # Ordenem segons l'ordre definit a AMICS
    friend_dict = {
        row["name"]: row["id"]
        for row in response.data
    }

    return [
        (friend_dict[name], name)
        for name in AMICS
        if name in friend_dict
    ]


def get_friend_id(name):

    response = (
        supabase
        .table("friends")
        .select("id")
        .eq("name", name)
        .single()
        .execute()
    )

    return response.data["id"]


# ============================================================
# VALOR D'UN VIATGE
# ============================================================

def trip_value(num_passengers, party, round_trip):

    if num_passengers <= 0:
        return 0.0

    value = float(num_passengers)

    # Festa = x2
    if party:
        value *= 2

        # Només si és festa:
        # anada + tornada = x2 addicional
        if round_trip:
            value *= 2

    return value


# ============================================================
# CALCULAR PUNTS
# ============================================================

def calculate_points():

    friends = get_friends()

    points = {
        friend_id: PUNTS_INICIALS
        for friend_id, _ in friends
    }

    trips_response = (
        supabase
        .table("trips")
        .select("*")
        .order("trip_date")
        .order("id")
        .execute()
    )

    trips = trips_response.data

    for trip in trips:

        passengers_response = (
            supabase
            .table("passengers")
            .select("friend_id")
            .eq("trip_id", trip["id"])
            .execute()
        )

        passenger_ids = [
            row["friend_id"]
            for row in passengers_response.data
        ]

        n = len(passenger_ids)

        if n == 0:
            continue

        total = trip_value(
            n,
            trip["party"],
            trip["round_trip"]
        )

        # Conductor guanya tot
        points[trip["driver_id"]] += total

        # Cada passatger perd només x/n
        loss_each = total / n

        for passenger_id in passenger_ids:

            if passenger_id in points:
                points[passenger_id] -= loss_each

    return points


# ============================================================
# AFEGIR VIATGE
# ============================================================

def add_trip(
    trip_date,
    driver_id,
    passenger_ids,
    round_trip,
    party,
    comment
):

    trip_response = (
        supabase
        .table("trips")
        .insert({
            "trip_date": str(trip_date),
            "driver_id": driver_id,
            "round_trip": round_trip,
            "party": party,
            "comment": comment
        })
        .execute()
    )

    trip_id = trip_response.data[0]["id"]

    passengers = [
        {
            "trip_id": trip_id,
            "friend_id": passenger_id
        }
        for passenger_id in passenger_ids
    ]

    if passengers:

        (
            supabase
            .table("passengers")
            .insert(passengers)
            .execute()
        )


# ============================================================
# ELIMINAR VIATGE
# ============================================================

def delete_trip(trip_id):

    (
        supabase
        .table("passengers")
        .delete()
        .eq("trip_id", trip_id)
        .execute()
    )

    (
        supabase
        .table("trips")
        .delete()
        .eq("id", trip_id)
        .execute()
    )


# ============================================================
# HISTORIAL
# ============================================================

def get_history():

    trips = (
        supabase
        .table("trips")
        .select("*")
        .order("trip_date", desc=True)
        .order("id", desc=True)
        .execute()
    ).data

    friends = get_friends()

    friend_names = {
        friend_id: name
        for friend_id, name in friends
    }

    result = []

    for trip in trips:

        passenger_rows = (
            supabase
            .table("passengers")
            .select("friend_id")
            .eq("trip_id", trip["id"])
            .execute()
        ).data

        passenger_names = [
            friend_names[row["friend_id"]]
            for row in passenger_rows
            if row["friend_id"] in friend_names
        ]

        result.append({
            "id": trip["id"],
            "date": trip["trip_date"],
            "driver": friend_names.get(
                trip["driver_id"],
                "Desconegut"
            ),
            "passengers": passenger_names,
            "round_trip": trip["round_trip"],
            "party": trip["party"],
            "comment": trip["comment"] or ""
        })

    return result


# ============================================================
# TÍTOL
# ============================================================

st.title("🚗 COTXE DE FESTA")

st.caption(
    "Qui ha fet més cotxe? Qui té més punts? "
    "Avui la ruleta decideix."
)

friends = get_friends()

if len(friends) != len(AMICS):

    st.error(
        "No s'han pogut carregar tots els amics."
    )

    st.stop()

points = calculate_points()


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "🎰 SORTEIG",
    "📝 AFEGIR VIATGE",
    "🏆 CLASSIFICACIÓ",
    "📜 HISTORIAL"
])


# ============================================================
# SORTEIG
# ============================================================

with tab1:

    st.header("🎰 Sorteig del conductor")

    st.write(
        "Selecciona **només les persones que van avui**. "
        "La ruleta donarà menys probabilitat als que tenen "
        "més punts."
    )

    selected_names = st.multiselect(
        "Qui ve avui?",
        [name for _, name in friends],
        default=[]
    )

    if len(selected_names) < 2:

        st.info(
            "Selecciona almenys 2 persones per poder fer "
            "el sorteig."
        )

    else:

        selected = []

        for friend_id, name in friends:

            if name in selected_names:

                selected.append({
                    "id": friend_id,
                    "name": name,
                    "points": points[friend_id]
                })

        # ----------------------------------------------------
        # PESOS
        # Més punts = MENYS probabilitat
        #
        # p = 1 / punts^2
        # ----------------------------------------------------

        weights = []

        for person in selected:

            p = max(
                person["points"],
                1.0
            )

            weight = 1 / (
                p ** EXPONENT_RULETA
            )

            weights.append(weight)

        total_weight = sum(weights)

        st.subheader("🎯 Probabilitats")

        cols = st.columns(
            min(4, len(selected))
        )

        for i, person in enumerate(selected):

            probability = (
                weights[i]
                / total_weight
                * 100
            )

            with cols[i % len(cols)]:

                st.metric(
                    person["name"],
                    f"{probability:.1f}%",
                    f"{person['points']:.1f} punts"
                )

        st.divider()

        # ----------------------------------------------------
        # SORTEIG
        # ----------------------------------------------------

        if st.button(
            "🎰 SORTEJAR CONDUCTOR",
            type="primary",
            use_container_width=True
        ):

            winner_index = random.choices(
                range(len(selected)),
                weights=weights,
                k=1
            )[0]

            winner = selected[winner_index]["name"]

            st.session_state["winner"] = winner

        # ----------------------------------------------------
        # RESULTAT
        # ----------------------------------------------------

        if "winner" in st.session_state:

            st.balloons()

            st.markdown(
                f"""
                <div style="
                    text-align:center;
                    padding:35px;
                    border-radius:20px;
                    background-color:#f0f2f6;
                    margin-top:20px;
                ">
                    <h1>🚗</h1>
                    <h2>FA COTXE...</h2>
                    <h1>{st.session_state["winner"].upper()}</h1>
                    <h3>🎉🎉🎉</h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")

            if st.button(
                "🔄 Tornar a sortejar",
                use_container_width=True
            ):

                del st.session_state["winner"]

                st.rerun()


# ============================================================
# AFEGIR VIATGE
# ============================================================

with tab2:

    st.header("📝 Afegir viatge")

    names = [
        name for _, name in friends
    ]

    driver_name = st.selectbox(
        "🚗 Conductor",
        names,
        key="add_driver"
    )

    available_passengers = [
        name
        for name in names
        if name != driver_name
    ]

    passenger_names = st.multiselect(
        "👥 Passatgers",
        available_passengers,
        key="add_passengers"
    )

    col1, col2 = st.columns(2)

    with col1:

        party = st.checkbox(
            "🎉 Festa",
            key="add_party"
        )

    with col2:

        round_trip = st.checkbox(
            "🔄 Anada i tornada",
            key="add_round_trip"
        )

    trip_date = st.date_input(
        "📅 Data",
        date.today(),
        key="add_date"
    )

    comment = st.text_area(
        "💬 Comentari (opcional)",
        key="add_comment"
    )

    # --------------------------------------------------------
    # INFORMACIÓ DE PUNTS
    # --------------------------------------------------------

    if passenger_names:

        value = trip_value(
            len(passenger_names),
            party,
            round_trip
        )

        loss = (
            value
            / len(passenger_names)
        )

        st.info(
            f"🚗 **{driver_name}: +{value:.1f} punts**\n\n"
            f"👥 Cada passatger: **-{loss:.1f} punts**"
        )

    # --------------------------------------------------------
    # BOTÓ
    # --------------------------------------------------------

    if st.button(
        "➡️ CONTINUAR",
        type="primary",
        use_container_width=True
    ):

        if not passenger_names:

            st.error(
                "Has de seleccionar almenys un passatger."
            )

        else:

            st.session_state[
                "pending_trip"
            ] = {
                "driver_name": driver_name,
                "passenger_names": passenger_names,
                "party": party,
                "round_trip": round_trip,
                "trip_date": trip_date,
                "comment": comment
            }

            st.rerun()

    # --------------------------------------------------------
    # CONFIRMACIÓ
    # --------------------------------------------------------

    if "pending_trip" in st.session_state:

        pending = st.session_state[
            "pending_trip"
        ]

        st.divider()

        st.warning(
            "⚠️ **CONFIRMA EL VIATGE**"
        )

        st.write(
            f"🚗 **Conductor:** "
            f"{pending['driver_name']}"
        )

        st.write(
            f"👥 **Passatgers:** "
            f"{', '.join(pending['passenger_names'])}"
        )

        st.write(
            f"📅 **Data:** "
            f"{pending['trip_date'].strftime('%d/%m/%Y')}"
        )

        st.write(
            f"🎉 **Festa:** "
            f"{'Sí' if pending['party'] else 'No'}"
        )

        st.write(
            f"🔄 **Anada i tornada:** "
            f"{'Sí' if pending['round_trip'] else 'No'}"
        )

        if pending["comment"].strip():

            st.write(
                f"💬 **Comentari:** "
                f"{pending['comment']}"
            )

        value = trip_value(
            len(pending["passenger_names"]),
            pending["party"],
            pending["round_trip"]
        )

        loss = (
            value
            / len(pending["passenger_names"])
        )

        st.success(
            f"🚗 {pending['driver_name']} "
            f"guanya **+{value:.1f} punts**"
        )

        st.warning(
            f"👥 Cada passatger perd "
            f"**-{loss:.1f} punts**"
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "❌ CANCEL·LAR",
                use_container_width=True
            ):

                del st.session_state[
                    "pending_trip"
                ]

                st.rerun()

        with col2:

            if st.button(
                "✅ CONFIRMAR VIATGE",
                type="primary",
                use_container_width=True
            ):

                driver_id = get_friend_id(
                    pending["driver_name"]
                )

                passenger_ids = [
                    get_friend_id(name)
                    for name in pending["passenger_names"]
                ]

                add_trip(
                    pending["trip_date"],
                    driver_id,
                    passenger_ids,
                    pending["round_trip"],
                    pending["party"],
                    pending["comment"].strip()
                )

                del st.session_state[
                    "pending_trip"
                ]

                st.session_state[
                    "trip_added"
                ] = True

                st.rerun()

    if st.session_state.pop(
        "trip_added",
        False
    ):

        st.success(
            "✅ VIATGE AFEGIT CORRECTAMENT!"
        )


# ============================================================
# CLASSIFICACIÓ
# ============================================================

with tab3:

    st.header("🏆 Classificació")

    ranking = []

    for friend_id, name in friends:

        ranking.append({
            "name": name,
            "points": points[friend_id]
        })

    ranking.sort(
        key=lambda x: x["points"],
        reverse=True
    )

    # --------------------------------------------------------
    # PODI
    # --------------------------------------------------------

    if len(ranking) >= 3:

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "🥈 2n",
                ranking[1]["name"],
                f"{ranking[1]['points']:.1f} punts"
            )

        with col2:

            st.metric(
                "🥇 1r",
                ranking[0]["name"],
                f"{ranking[0]['points']:.1f} punts"
            )

        with col3:

            st.metric(
                "🥉 3r",
                ranking[2]["name"],
                f"{ranking[2]['points']:.1f} punts"
            )

    st.divider()

    # --------------------------------------------------------
    # CLASSIFICACIÓ COMPLETA
    # --------------------------------------------------------

    for i, person in enumerate(ranking):

        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"**{i + 1}.**"

        st.markdown(
            f"### {medal} {person['name']}"
        )

        st.progress(
            max(
                0.0,
                min(
                    person["points"] / 200,
                    1.0
                )
            )
        )

        st.write(
            f"**{person['points']:.1f} punts**"
        )


# ============================================================
# HISTORIAL
# ============================================================

with tab4:

    st.header("📜 Historial de viatges")

    history = get_history()

    if not history:

        st.info(
            "Encara no hi ha cap viatge registrat."
        )

    for trip in history:

        st.markdown(
            f"### 🚗 {trip['driver']} "
            f"— {trip['date']}"
        )

        st.write(
            "👥 **Passatgers:** "
            + ", ".join(trip["passengers"])
        )

        extras = []

        if trip["party"]:
            extras.append("🎉 Festa")

        if trip["round_trip"]:
            extras.append("🔄 Anada i tornada")

        if extras:

            st.write(
                " · ".join(extras)
            )

        value = trip_value(
            len(trip["passengers"]),
            trip["party"],
            trip["round_trip"]
        )

        loss = (
            value
            / len(trip["passengers"])
            if trip["passengers"]
            else 0
        )

        st.write(
            f"💰 Conductor: **+{value:.1f}** "
            f"· Passatgers: **-{loss:.1f} cadascun**"
        )

        if trip["comment"]:

            st.caption(
                f"💬 {trip['comment']}"
            )

        st.divider()

        # ----------------------------------------------------
        # ELIMINAR
        # ----------------------------------------------------

        if st.button(
            "🗑️ ELIMINAR VIATGE",
            key=f"delete_button_{trip['id']}",
            use_container_width=True
        ):

            st.session_state[
                "pending_delete"
            ] = trip["id"]

            st.rerun()

        # ----------------------------------------------------
        # CONFIRMACIÓ ELIMINACIÓ
        # ----------------------------------------------------

        if st.session_state.get(
            "pending_delete"
        ) == trip["id"]:

            st.warning(
                "⚠️ **ESTÀS SEGUR QUE VOLS "
                "ELIMINAR AQUEST VIATGE?**"
            )

            st.write(
                "Els punts de tots els afectats "
                "es recalcularan automàticament."
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "❌ CANCEL·LAR",
                    key=f"cancel_delete_{trip['id']}",
                    use_container_width=True
                ):

                    del st.session_state[
                        "pending_delete"
                    ]

                    st.rerun()

            with col2:

                if st.button(
                    "🗑️ SÍ, ELIMINAR",
                    key=f"confirm_delete_{trip['id']}",
                    type="primary",
                    use_container_width=True
                ):

                    delete_trip(
                        trip["id"]
                    )

                    del st.session_state[
                        "pending_delete"
                    ]

                    st.session_state[
                        "trip_deleted"
                    ] = True

                    st.rerun()


    if st.session_state.pop(
        "trip_deleted",
        False
    ):

        st.success(
            "✅ VIATGE ELIMINAT CORRECTAMENT!"
        )
