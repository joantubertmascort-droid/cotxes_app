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
    "Tubert", "Miralles", "Magaña", "Hector", "Adri",
    "Porsell", "Gugu", "Carbo", "Hicham", "Younes",
    "Pablo", "Biel", "Isma"
]

PUNTS_INICIALS = 100

# Com més gran, més exagerada és la diferència.
EXPONENT_RULETA = 2


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
# AMICS
# ============================================================

def get_friends():

    response = (
        supabase
        .table("friends")
        .select("id,name")
        .order("id")
        .execute()
    )

    return [
        (row["id"], row["name"])
        for row in response.data
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
# VALOR DEL VIATGE
# ============================================================

def trip_value(num_passengers, party, round_trip):

    if num_passengers == 0:
        return 0

    value = num_passengers

    if party:

        value *= 2

        if round_trip:
            value *= 2

    return value


# ============================================================
# CALCULAR PUNTS
# ============================================================

def calculate_points():

    friends = get_friends()

    points = {
        friend_id: float(PUNTS_INICIALS)
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

        points[trip["driver_id"]] += total

        loss_each = total / n

        for passenger_id in passenger_ids:
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
            "trip_date": trip_date,
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

    supabase.table(
        "passengers"
    ).insert(passengers).execute()


# ============================================================
# ELIMINAR VIATGE
# ============================================================

def delete_trip(trip_id):

    supabase \
        .table("passengers") \
        .delete() \
        .eq("trip_id", trip_id) \
        .execute()

    supabase \
        .table("trips") \
        .delete() \
        .eq("id", trip_id) \
        .execute()


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
        ]

        result.append({
            "id": trip["id"],
            "date": trip["trip_date"],
            "driver": friend_names[trip["driver_id"]],
            "passengers": passenger_names,
            "round_trip": trip["round_trip"],
            "party": trip["party"],
            "comment": trip["comment"]
        })

    return result


# ============================================================
# TÍTOL
# ============================================================

st.title("🚗 COTXE DE FESTA")

st.caption(
    "Punts, classificació i sorteig del conductor."
)

friends = get_friends()
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

    selected_names = st.multiselect(
        "Selecciona qui està disponible avui:",
        [name for _, name in friends],
        default=[name for _, name in friends]
    )

    if len(selected_names) < 2:

        st.warning(
            "Selecciona almenys 2 persones."
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

        weights = []

        for person in selected:

            p = max(
                person["points"],
                0.1
            )

            weights.append(
                1 / (p ** EXPONENT_RULETA)
            )

        total_weight = sum(weights)

        st.subheader("📊 Probabilitats")

        cols = st.columns(
            min(4, len(selected))
        )

        for i, person in enumerate(selected):

            probability = (
                weights[i] /
                total_weight *
                100
            )

            with cols[i % len(cols)]:

                st.metric(
                    person["name"],
                    f"{probability:.1f}%",
                    f"{person['points']:.1f} punts"
                )

        st.divider()

        if st.button(
            "🎰 SORTEJAR",
            type="primary",
            use_container_width=True
        ):

            names = [
                person["name"]
                for person in selected
            ]

            winner = random.choices(
                names,
                weights=weights,
                k=1
            )[0]

            st.session_state["winner"] = winner

        if "winner" in st.session_state:

            st.balloons()

            st.success(
                f"🚗 **{st.session_state['winner'].upper()} "
                f"FA COTXE!**"
            )

            if st.button("🔄 Tornar a sortejar"):

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
        "🚗 Conductor:",
        names
    )

    passenger_names = st.multiselect(
        "👥 Passatgers:",
        [
            name
            for name in names
            if name != driver_name
        ]
    )

    col1, col2 = st.columns(2)

    with col1:

        party = st.checkbox(
            "🎉 Festa"
        )

    with col2:

        round_trip = st.checkbox(
            "🔄 Anada i tornada"
        )

    trip_date = st.date_input(
        "📅 Data:",
        date.today()
    )

    comment = st.text_area(
        "💬 Comentari (opcional)"
    )

    value = trip_value(
        len(passenger_names),
        party,
        round_trip
    )

    if passenger_names:

        loss = value / len(passenger_names)

        st.info(
            f"🚗 {driver_name}: **+{value:.1f} punts**\n\n"
            f"👥 Cada passatger: **-{loss:.1f} punts**"
        )

    if st.button(
        "💾 CONTINUAR",
        type="primary",
        use_container_width=True
    ):

        if not passenger_names:

            st.error(
                "Selecciona almenys un passatger."
            )

        else:

            st.session_state["confirm_add"] = True


    if st.session_state.get(
        "confirm_add",
        False
    ):

        @st.dialog("⚠️ Confirmar viatge")
        def confirm_add():

            st.write(
                "Estàs segur que vols afegir aquest viatge?"
            )

            st.divider()

            st.write(
                f"🚗 **Conductor:** {driver_name}"
            )

            st.write(
                f"👥 **Passatgers:** "
                f"{', '.join(passenger_names)}"
            )

            st.write(
                f"📅 **Data:** "
                f"{trip_date.strftime('%d/%m/%Y')}"
            )

            st.write(
                f"🎉 **Festa:** "
                f"{'Sí' if party else 'No'}"
            )

            st.write(
                f"🔄 **Anada i tornada:** "
                f"{'Sí' if round_trip else 'No'}"
            )

            if comment.strip():

                st.write(
                    f"💬 **Comentari:** {comment}"
                )

            st.divider()

            loss = value / len(passenger_names)

            st.success(
                f"🚗 {driver_name}: +{value:.1f}"
            )

            st.warning(
                f"👥 Cada passatger: -{loss:.1f}"
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "❌ Cancel·lar"
                ):

                    st.session_state[
                        "confirm_add"
                    ] = False

                    st.rerun()

            with col2:

                if st.button(
                    "✅ CONFIRMAR",
                    type="primary"
                ):

                    driver_id = get_friend_id(
                        driver_name
                    )

                    passenger_ids = [
                        get_friend_id(name)
                        for name in passenger_names
                    ]

                    add_trip(
                        str(trip_date),
                        driver_id,
                        passenger_ids,
                        round_trip,
                        party,
                        comment.strip()
                    )

                    st.session_state[
                        "confirm_add"
                    ] = False

                    st.session_state[
                        "added"
                    ] = True

                    st.rerun()

        confirm_add()


    if st.session_state.pop(
        "added",
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

    for i, person in enumerate(ranking):

        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"{i + 1}."

        st.markdown(
            f"### {medal} {person['name']}"
        )

        st.write(
            f"**{person['points']:.1f} punts**"
        )


# ============================================================
# HISTORIAL
# ============================================================

with tab4:

    st.header("📜 Historial")

    history = get_history()

    if not history:

        st.info(
            "Encara no hi ha viatges."
        )

    for trip in history:

        st.markdown(
            f"### 🚗 {trip['driver']} — {trip['date']}"
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
            st.write(" · ".join(extras))

        value = trip_value(
            len(trip["passengers"]),
            trip["party"],
            trip["round_trip"]
        )

        loss = (
            value / len(trip["passengers"])
            if trip["passengers"]
            else 0
        )

        st.write(
            f"💰 Conductor +{value:.1f} · "
            f"Passatgers -{loss:.1f} cadascun"
        )

        if trip["comment"]:
            st.caption(
                f"💬 {trip['comment']}"
            )

        if st.button(
            "🗑️ ELIMINAR",
            key=f"delete_{trip['id']}"
        ):

            st.session_state[
                "delete_id"
            ] = trip["id"]

            st.rerun()


        if st.session_state.get(
            "delete_id"
        ) == trip["id"]:

            @st.dialog("⚠️ Eliminar viatge")
            def confirm_delete():

                st.warning(
                    "Estàs segur que vols eliminar aquest viatge?"
                )

                st.write(
                    "Els punts es recalcularan "
                    "automàticament."
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button("❌ Cancel·lar"):

                        del st.session_state[
                            "delete_id"
                        ]

                        st.rerun()

                with col2:

                    if st.button(
                        "🗑️ ELIMINAR",
                        type="primary"
                    ):

                        delete_trip(
                            trip["id"]
                        )

                        del st.session_state[
                            "delete_id"
                        ]

                        st.session_state[
                            "deleted"
                        ] = True

                        st.rerun()

            confirm_delete()

        st.divider()


    if st.session_state.pop(
        "deleted",
        False
    ):

        st.success(
            "✅ VIATGE ELIMINAT!"
        )
