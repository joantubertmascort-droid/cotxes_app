```python
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

# Com més alt, més exagerada és la diferència
# de probabilitats de la ruleta.
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
# AMICS
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


def get_friends():

    response = (
        supabase
        .table("friends")
        .select("id,name")
        .execute()
    )

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
# CÀLCUL DEL VALOR D'UN VIATGE
# ============================================================

def trip_value_default(
    num_passengers,
    party,
    round_trip
):

    if num_passengers <= 0:
        return 0.0

    value = float(num_passengers)

    # Festa = x2
    if party:

        value *= 2

        # Anada i tornada només té efecte
        # si és festa
        if round_trip:
            value *= 2

    return value


# ============================================================
# OBTENIR TOTS ELS VIATGES
# ============================================================

def get_trips():

    return (
        supabase
        .table("trips")
        .select("*")
        .order("trip_date")
        .order("id")
        .execute()
    ).data


# ============================================================
# OBTENIR PASSATGERS D'UN VIATGE
# ============================================================

def get_passenger_ids(trip_id):

    response = (
        supabase
        .table("passengers")
        .select("friend_id")
        .eq("trip_id", trip_id)
        .execute()
    )

    return [
        row["friend_id"]
        for row in response.data
    ]


# ============================================================
# CALCULAR PUNTS
# ============================================================

def calculate_points():

    friends = get_friends()

    points = {
        friend_id: PUNTS_INICIALS
        for friend_id, _ in friends
    }

    # --------------------------------------------------------
    # VIATGES
    # --------------------------------------------------------

    trips = get_trips()

    for trip in trips:

        passenger_ids = get_passenger_ids(
            trip["id"]
        )

        n = len(passenger_ids)

        if n == 0:
            continue

        # ----------------------------------------------------
        # Si el viatge té punts personalitzats,
        # aquests prevalen.
        # ----------------------------------------------------

        custom_points = trip.get(
            "custom_points_per_passenger"
        )

        if custom_points is not None:

            try:
                points_per_passenger = float(
                    custom_points
                )
            except:
                points_per_passenger = 0.0

            total = (
                points_per_passenger * n
            )

        else:

            total = trip_value_default(
                n,
                trip["party"],
                trip["round_trip"]
            )

        # Conductor guanya el total
        points[trip["driver_id"]] += total

        # Cada passatger perd x/n
        loss_each = total / n

        for passenger_id in passenger_ids:

            if passenger_id in points:

                points[passenger_id] -= loss_each

    # --------------------------------------------------------
    # TRADEOS DE PUNTS
    # --------------------------------------------------------

    transfers = (
        supabase
        .table("point_transfers")
        .select("*")
        .order("transfer_date")
        .order("id")
        .execute()
    ).data

    for transfer in transfers:

        from_id = transfer["from_friend_id"]
        to_id = transfer["to_friend_id"]
        amount = float(transfer["points"])

        if from_id in points:
            points[from_id] -= amount

        if to_id in points:
            points[to_id] += amount

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
    comment,
    custom_points
):

    trip_data = {
        "trip_date": str(trip_date),
        "driver_id": driver_id,
        "round_trip": round_trip,
        "party": party,
        "comment": comment
    }

    if custom_points is not None:
        trip_data[
            "custom_points_per_passenger"
        ] = custom_points

    trip_response = (
        supabase
        .table("trips")
        .insert(trip_data)
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
# AFEGIR TRADEO
# ============================================================

def add_transfer(
    from_id,
    to_id,
    points,
    transfer_date,
    comment
):

    (
        supabase
        .table("point_transfers")
        .insert({
            "from_friend_id": from_id,
            "to_friend_id": to_id,
            "points": points,
            "transfer_date": str(
                transfer_date
            ),
            "comment": comment
        })
        .execute()
    )


# ============================================================
# ELIMINAR TRADEO
# ============================================================

def delete_transfer(transfer_id):

    (
        supabase
        .table("point_transfers")
        .delete()
        .eq("id", transfer_id)
        .execute()
    )


# ============================================================
# HISTORIAL DE VIATGES
# ============================================================

def get_trip_history():

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
            "comment": trip["comment"] or "",
            "custom_points": trip.get(
                "custom_points_per_passenger"
            )
        })

    return result


# ============================================================
# HISTORIAL DE TRADEOS
# ============================================================

def get_transfer_history():

    transfers = (
        supabase
        .table("point_transfers")
        .select("*")
        .order("transfer_date", desc=True)
        .order("id", desc=True)
        .execute()
    ).data

    friends = get_friends()

    friend_names = {
        friend_id: name
        for friend_id, name in friends
    }

    result = []

    for transfer in transfers:

        result.append({
            "id": transfer["id"],
            "date": transfer["transfer_date"],
            "from": friend_names.get(
                transfer["from_friend_id"],
                "Desconegut"
            ),
            "to": friend_names.get(
                transfer["to_friend_id"],
                "Desconegut"
            ),
            "points": float(
                transfer["points"]
            ),
            "comment": transfer["comment"] or ""
        })

    return result


# ============================================================
# TÍTOL
# ============================================================

st.title("🚗 COTXE DE FESTA")

st.caption(
    "Punts, viatges i sorteigs. "
    "Que la ruleta decideixi qui condueix."
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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎰 SORTEIG",
    "📝 AFEGIR VIATGE",
    "💸 TRADEO DE PUNTS",
    "🏆 CLASSIFICACIÓ",
    "📜 HISTORIAL"
])


# ============================================================
# SORTEIG
# ============================================================

with tab1:

    st.header("🎰 Sorteig del conductor")

    st.write(
        "Selecciona qui surt avui. "
        "Els que tenen més punts tenen menys "
        "probabilitats de fer cotxe."
    )

    selected_names = st.multiselect(
        "Qui ve avui?",
        [name for _, name in friends],
        default=[]
    )

    if len(selected_names) < 2:

        st.info(
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

        # ----------------------------------------------------
        # PESOS
        #
        # Més punts = MENYS probabilitat
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

            winner = selected[
                winner_index
            ]["name"]

            st.session_state[
                "winner"
            ] = winner

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
                    <h1>
                        {st.session_state["winner"].upper()}
                    </h1>
                    <h3>🎉🎉🎉</h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "🔄 Tornar a sortejar",
                use_container_width=True
            ):

                del st.session_state[
                    "winner"
                ]

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

    # --------------------------------------------------------
    # NOU: PUNTS PERSONALITZATS
    # --------------------------------------------------------

    custom_mode = st.selectbox(
        "💰 Punts per passatger",
        [
            "Per defecte",
            "Personalitzat"
        ],
        key="custom_points_mode"
    )

    custom_points = None

    if custom_mode == "Personalitzat":

        custom_points = st.number_input(
            "Punts que traspassa cada passatger "
            "al conductor",
            min_value=0.01,
            step=0.5,
            value=1.0,
            key="custom_points_value"
        )

        st.caption(
            "⚠️ Aquest valor preval sobre Festa "
            "i Anada i tornada."
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
    # PREVISUALITZACIÓ
    # --------------------------------------------------------

    if passenger_names:

        if custom_points is not None:

            value = (
                custom_points
                * len(passenger_names)
            )

            loss = custom_points

            st.info(
                f"🚗 **{driver_name}: "
                f"+{value:.1f} punts**\n\n"
                f"👥 Cada passatger: "
                f"**-{loss:.1f} punts**"
            )

        else:

            value = trip_value_default(
                len(passenger_names),
                party,
                round_trip
            )

            loss = (
                value
                / len(passenger_names)
            )

            st.info(
                f"🚗 **{driver_name}: "
                f"+{value:.1f} punts**\n\n"
                f"👥 Cada passatger: "
                f"**-{loss:.1f} punts**"
            )

    # --------------------------------------------------------
    # CONTINUAR
    # --------------------------------------------------------

    if st.button(
        "➡️ CONTINUAR",
        type="primary",
        use_container_width=True
    ):

        if not passenger_names:

            st.error(
                "Has de seleccionar almenys "
                "un passatger."
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
                "comment": comment,
                "custom_points": custom_points
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
            "⚠️ CONFIRMA EL VIATGE"
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

        if pending["custom_points"] is not None:

            st.write(
                f"💰 **Punts personalitzats:** "
                f"{pending['custom_points']:.1f} "
                f"per passatger"
            )

            total = (
                pending["custom_points"]
                * len(
                    pending["passenger_names"]
                )
            )

            st.success(
                f"🚗 El conductor guanya "
                f"**+{total:.1f} punts**"
            )

            st.warning(
                f"👥 Cada passatger perd "
                f"**-{pending['custom_points']:.1f} punts**"
            )

        else:

            total = trip_value_default(
                len(
                    pending["passenger_names"]
                ),
                pending["party"],
                pending["round_trip"]
            )

            loss = (
                total
                / len(
                    pending["passenger_names"]
                )
            )

            st.success(
                f"🚗 El conductor guanya "
                f"**+{total:.1f} punts**"
            )

            st.warning(
                f"👥 Cada passatger perd "
                f"**-{loss:.1f} punts**"
            )

        if pending["comment"].strip():

            st.write(
                f"💬 **Comentari:** "
                f"{pending['comment']}"
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
                    for name in pending[
                        "passenger_names"
                    ]
                ]

                add_trip(
                    pending["trip_date"],
                    driver_id,
                    passenger_ids,
                    pending["round_trip"],
                    pending["party"],
                    pending["comment"].strip(),
                    pending["custom_points"]
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
# TRADEO DE PUNTS
# ============================================================

with tab3:

    st.header("💸 Tradeo de Punts")

    st.write(
        "Traspassa lliurement punts entre qualsevol "
        "persona del grup."
    )

    names = [
        name for _, name in friends
    ]

    from_name = st.selectbox(
        "👤 Qui traspassa?",
        names,
        key="transfer_from"
    )

    to_names = [
        name
        for name in names
        if name != from_name
    ]

    to_name = st.selectbox(
        "➡️ A qui?",
        to_names,
        key="transfer_to"
    )

    transfer_points = st.number_input(
        "💰 Quants punts?",
        min_value=0.01,
        step=0.5,
        value=1.0,
        key="transfer_points"
    )

    transfer_date = st.date_input(
        "📅 Data",
        date.today(),
        key="transfer_date"
    )

    transfer_comment = st.text_area(
        "💬 Comentari (opcional)",
        key="transfer_comment"
    )

    st.info(
        f"**{from_name}** → "
        f"**{transfer_points:.1f} punts** → "
        f"**{to_name}**"
    )

    if st.button(
        "➡️ CONTINUAR",
        type="primary",
        use_container_width=True
    ):

        if transfer_points <= 0:

            st.error(
                "Els punts han de ser superiors a 0."
            )

        else:

            st.session_state[
                "pending_transfer"
            ] = {
                "from_name": from_name,
                "to_name": to_name,
                "points": transfer_points,
                "date": transfer_date,
                "comment": transfer_comment
            }

            st.rerun()

    # --------------------------------------------------------
    # CONFIRMACIÓ
    # --------------------------------------------------------

    if "pending_transfer" in st.session_state:

        pending = st.session_state[
            "pending_transfer"
        ]

        st.divider()

        st.warning(
            "⚠️ CONFIRMA EL TRADEO"
        )

        st.write(
            f"👤 **Qui traspassa:** "
            f"{pending['from_name']}"
        )

        st.write(
            f"➡️ **Qui rep:** "
            f"{pending['to_name']}"
        )

        st.write(
            f"💰 **Punts:** "
            f"{pending['points']:.1f}"
        )

        st.write(
            f"📅 **Data:** "
            f"{pending['date'].strftime('%d/%m/%Y')}"
        )

        if pending["comment"].strip():

            st.write(
                f"💬 **Comentari:** "
                f"{pending['comment']}"
            )

        st.error(
            f"⚠️ {pending['from_name']} "
            f"perdrà {pending['points']:.1f} punts "
            f"i {pending['to_name']} "
            f"en guanyarà {pending['points']:.1f}."
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "❌ CANCEL·LAR",
                key="cancel_transfer",
                use_container_width=True
            ):

                del st.session_state[
                    "pending_transfer"
                ]

                st.rerun()

        with col2:

            if st.button(
                "✅ CONFIRMAR TRADEO",
                type="primary",
                key="confirm_transfer",
                use_container_width=True
            ):

                from_id = get_friend_id(
                    pending["from_name"]
                )

                to_id = get_friend_id(
                    pending["to_name"]
                )

                add_transfer(
                    from_id,
                    to_id,
                    pending["points"],
                    pending["date"],
                    pending["comment"].strip()
                )

                del st.session_state[
                    "pending_transfer"
                ]

                st.session_state[
                    "transfer_added"
                ] = True

                st.rerun()

    if st.session_state.pop(
        "transfer_added",
        False
    ):

        st.success(
            "✅ TRADEO FET CORRECTAMENT!"
        )


# ============================================================
# CLASSIFICACIÓ
# ============================================================

with tab4:

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

with tab5:

    st.header("📜 Historial")

    history_type = st.radio(
        "Mostrar",
        [
            "🚗 Viatges",
            "💸 Tradeos"
        ],
        horizontal=True
    )

    # ========================================================
    # HISTORIAL VIATGES
    # ========================================================

    if history_type == "🚗 Viatges":

        history = get_trip_history()

        if not history:

            st.info(
                "Encara no hi ha cap viatge."
            )

        for trip in history:

            st.markdown(
                f"### 🚗 {trip['driver']} "
                f"— {trip['date']}"
            )

            st.write(
                "👥 **Passatgers:** "
                + ", ".join(
                    trip["passengers"]
                )
            )

            extras = []

            if trip["party"]:
                extras.append("🎉 Festa")

            if trip["round_trip"]:
                extras.append(
                    "🔄 Anada i tornada"
                )

            if extras:

                st.write(
                    " · ".join(extras)
                )

            # ------------------------------------------------
            # PUNTS
            # ------------------------------------------------

            if trip["custom_points"] is not None:

                custom = float(
                    trip["custom_points"]
                )

                st.write(
                    f"💰 **Personalitzat:** "
                    f"{custom:.1f} punts "
                    f"per passatger"
                )

                st.write(
                    f"🚗 Conductor: "
                    f"**+{custom * len(trip['passengers']):.1f}** "
                    f"· Passatgers: "
                    f"**-{custom:.1f} cadascun**"
                )

            else:

                value = trip_value_default(
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
                    f"💰 Conductor: "
                    f"**+{value:.1f}** "
                    f"· Passatgers: "
                    f"**-{loss:.1f} cadascun**"
                )

            if trip["comment"]:

                st.caption(
                    f"💬 {trip['comment']}"
                )

            # ------------------------------------------------
            # ELIMINAR
            # ------------------------------------------------

            if st.button(
                "🗑️ ELIMINAR VIATGE",
                key=f"delete_trip_{trip['id']}",
                use_container_width=True
            ):

                st.session_state[
                    "pending_delete_trip"
                ] = trip["id"]

                st.rerun()

            if st.session_state.get(
                "pending_delete_trip"
            ) == trip["id"]:

                st.warning(
                    "⚠️ ESTÀS SEGUR QUE VOLS "
                    "ELIMINAR AQUEST VIATGE?"
                )

                st.write(
                    "Els punts es recalcularan "
                    "automàticament."
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "❌ CANCEL·LAR",
                        key=f"cancel_trip_{trip['id']}",
                        use_container_width=True
                    ):

                        del st.session_state[
                            "pending_delete_trip"
                        ]

                        st.rerun()

                with col2:

                    if st.button(
                        "🗑️ SÍ, ELIMINAR",
                        key=f"confirm_trip_{trip['id']}",
                        type="primary",
                        use_container_width=True
                    ):

                        delete_trip(
                            trip["id"]
                        )

                        del st.session_state[
                            "pending_delete_trip"
                        ]

                        st.session_state[
                            "trip_deleted"
                        ] = True

                        st.rerun()

            st.divider()

        if st.session_state.pop(
            "trip_deleted",
            False
        ):

            st.success(
                "✅ VIATGE ELIMINAT!"
            )

    # ========================================================
    # HISTORIAL TRADEOS
    # ========================================================

    else:

        transfers = get_transfer_history()

        if not transfers:

            st.info(
                "Encara no hi ha cap tradeo."
            )

        for transfer in transfers:

            st.markdown(
                f"### 💸 "
                f"{transfer['from']} → "
                f"{transfer['to']}"
            )

            st.write(
                f"💰 **{transfer['points']:.1f} punts**"
            )

            st.write(
                f"📅 {transfer['date']}"
            )

            if transfer["comment"]:

                st.caption(
                    f"💬 {transfer['comment']}"
                )

            if st.button(
                "🗑️ ELIMINAR TRADEO",
                key=f"delete_transfer_{transfer['id']}",
                use_container_width=True
            ):

                st.session_state[
                    "pending_delete_transfer"
                ] = transfer["id"]

                st.rerun()

            if st.session_state.get(
                "pending_delete_transfer"
            ) == transfer["id"]:

                st.warning(
                    "⚠️ ESTÀS SEGUR QUE VOLS "
                    "ELIMINAR AQUEST TRADEO?"
                )

                st.write(
                    "Els punts es recalcularan "
                    "automàticament."
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "❌ CANCEL·LAR",
                        key=f"cancel_transfer_delete_{transfer['id']}",
                        use_container_width=True
                    ):

                        del st.session_state[
                            "pending_delete_transfer"
                        ]

                        st.rerun()

                with col2:

                    if st.button(
                        "🗑️ SÍ, ELIMINAR",
                        key=f"confirm_transfer_delete_{transfer['id']}",
                        type="primary",
                        use_container_width=True
                    ):

                        delete_transfer(
                            transfer["id"]
                        )

                        del st.session_state[
                            "pending_delete_transfer"
                        ]

                        st.session_state[
                            "transfer_deleted"
                        ] = True

                        st.rerun()

            st.divider()

        if st.session_state.pop(
            "transfer_deleted",
            False
        ):

            st.success(
                "✅ TRADEO ELIMINAT!"
            )
