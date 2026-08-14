import streamlit as st
import sqlite3
import random
from datetime import date
import streamlit.components.v1 as components


# ============================================================
# CONFIGURACIÓ
# ============================================================

DB = "festa.db"

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

PUNTS_INICIALS = 100

# Com més alt, més castigada queda la probabilitat
# dels que tenen molts punts.
EXPONENT_RULETA = 2


# ============================================================
# CONFIGURACIÓ STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Cotxe de Festa",
    page_icon="🚗",
    layout="wide"
)


# ============================================================
# BASE DE DADES
# ============================================================

def get_connection():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_date TEXT NOT NULL,
            driver_id INTEGER NOT NULL,
            round_trip INTEGER NOT NULL DEFAULT 0,
            party INTEGER NOT NULL DEFAULT 0,
            comment TEXT,
            FOREIGN KEY(driver_id) REFERENCES friends(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passengers (
            trip_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            FOREIGN KEY(trip_id) REFERENCES trips(id),
            FOREIGN KEY(friend_id) REFERENCES friends(id)
        )
    """)

    conn.commit()

    for amic in AMICS:
        cursor.execute("""
            INSERT OR IGNORE INTO friends (name)
            VALUES (?)
        """, (amic,))

    conn.commit()
    conn.close()


init_db()


# ============================================================
# FUNCIONS BÀSIQUES
# ============================================================

def get_friends():

    conn = get_connection()

    result = conn.execute("""
        SELECT id, name
        FROM friends
        ORDER BY id
    """).fetchall()

    conn.close()

    return result


def get_friend_id(name):

    conn = get_connection()

    result = conn.execute("""
        SELECT id
        FROM friends
        WHERE name = ?
    """, (name,)).fetchone()

    conn.close()

    return result[0]


# ============================================================
# PUNTS DEL VIATGE
# ============================================================

def trip_value(num_passengers, party, round_trip):

    if num_passengers <= 0:
        return 0

    # 1 punt per passatger
    value = num_passengers

    # Festa
    if party:
        value *= 2

        # Festa + anada i tornada
        if round_trip:
            value *= 2

    return value


# ============================================================
# CALCULAR PUNTS ACTUALS
# ============================================================

def calculate_points():

    friends = get_friends()

    points = {
        friend_id: float(PUNTS_INICIALS)
        for friend_id, _ in friends
    }

    conn = get_connection()

    trips = conn.execute("""
        SELECT
            id,
            driver_id,
            round_trip,
            party
        FROM trips
        ORDER BY trip_date ASC, id ASC
    """).fetchall()

    for trip_id, driver_id, round_trip, party in trips:

        passengers = conn.execute("""
            SELECT friend_id
            FROM passengers
            WHERE trip_id = ?
        """, (trip_id,)).fetchall()

        passenger_ids = [
            passenger[0]
            for passenger in passengers
        ]

        n = len(passenger_ids)

        if n == 0:
            continue

        total_points = trip_value(
            n,
            party,
            round_trip
        )

        # Conductor guanya tots els punts
        points[driver_id] += total_points

        # Els passatgers comparteixen la pèrdua
        loss_each = total_points / n

        for passenger_id in passenger_ids:
            points[passenger_id] -= loss_each

    conn.close()

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

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO trips (
            trip_date,
            driver_id,
            round_trip,
            party,
            comment
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        trip_date,
        driver_id,
        int(round_trip),
        int(party),
        comment
    ))

    trip_id = cursor.lastrowid

    for passenger_id in passenger_ids:

        cursor.execute("""
            INSERT INTO passengers (
                trip_id,
                friend_id
            )
            VALUES (?, ?)
        """, (
            trip_id,
            passenger_id
        ))

    conn.commit()
    conn.close()


# ============================================================
# ELIMINAR VIATGE
# ============================================================

def delete_trip(trip_id):

    conn = get_connection()

    conn.execute("""
        DELETE FROM passengers
        WHERE trip_id = ?
    """, (trip_id,))

    conn.execute("""
        DELETE FROM trips
        WHERE id = ?
    """, (trip_id,))

    conn.commit()
    conn.close()


# ============================================================
# HISTORIAL
# ============================================================

def get_history():

    conn = get_connection()

    trips = conn.execute("""
        SELECT
            trips.id,
            trips.trip_date,
            trips.driver_id,
            trips.round_trip,
            trips.party,
            trips.comment,
            friends.name
        FROM trips
        JOIN friends
        ON trips.driver_id = friends.id
        ORDER BY trips.trip_date DESC, trips.id DESC
    """).fetchall()

    result = []

    for (
        trip_id,
        trip_date,
        driver_id,
        round_trip,
        party,
        comment,
        driver_name
    ) in trips:

        passengers = conn.execute("""
            SELECT friends.name
            FROM passengers
            JOIN friends
            ON passengers.friend_id = friends.id
            WHERE passengers.trip_id = ?
        """, (trip_id,)).fetchall()

        passenger_names = [
            p[0]
            for p in passengers
        ]

        result.append({
            "id": trip_id,
            "date": trip_date,
            "driver": driver_name,
            "passengers": passenger_names,
            "round_trip": bool(round_trip),
            "party": bool(party),
            "comment": comment
        })

    conn.close()

    return result


# ============================================================
# RULETA
# ============================================================

def show_wheel(names, winner):

    colors = [
        "#ff595e",
        "#ffca3a",
        "#8ac926",
        "#1982c4",
        "#6a4c93",
        "#f9844a",
        "#43aa8b",
        "#577590"
    ]

    section = 360 / len(names)

    winner_index = names.index(winner)

    target_angle = (
        360 * 7
        + (
            360
            - (
                winner_index * section
                + section / 2
            )
        )
    )

    gradient_parts = []

    for i in range(len(names)):

        color = colors[i % len(colors)]

        start = i * section
        end = (i + 1) * section

        gradient_parts.append(
            f"{color} {start}deg {end}deg"
        )

    gradient = ", ".join(gradient_parts)

    labels = ""

    for i, name in enumerate(names):

        angle = i * section + section / 2

        labels += f"""
        <div class="label"
             style="
                transform:
                rotate({angle}deg)
                translateY(-135px)
                rotate(-{angle}deg);
             ">
            {name}
        </div>
        """

    html = f"""
    <style>

    body {{
        margin: 0;
        background: transparent;
        font-family: Arial, sans-serif;
    }}

    .container {{
        width: 400px;
        height: 440px;
        margin: auto;
        position: relative;
    }}

    .pointer {{
        position: absolute;
        top: 0;
        left: 50%;

        transform: translateX(-50%);

        width: 0;
        height: 0;

        border-left: 15px solid transparent;
        border-right: 15px solid transparent;
        border-top: 35px solid black;

        z-index: 10;
    }}

    .wheel {{
        position: absolute;

        top: 30px;
        left: 20px;

        width: 360px;
        height: 360px;

        border-radius: 50%;

        background:
            conic-gradient({gradient});

        border: 8px solid #222;

        box-shadow:
            0 5px 20px rgba(0,0,0,0.25);

        transform: rotate(0deg);

        animation:
            spin 5s cubic-bezier(.12,.75,.15,1)
            forwards;
    }}

    .center {{
        position: absolute;

        top: 185px;
        left: 175px;

        width: 50px;
        height: 50px;

        border-radius: 50%;

        background: white;

        border: 5px solid #222;

        z-index: 5;
    }}

    .label {{
        position: absolute;

        top: 180px;
        left: 180px;

        width: 1px;
        height: 1px;

        font-weight: bold;
        font-size: 14px;

        white-space: nowrap;

        transform-origin: 0 0;
    }}

    @keyframes spin {{

        from {{
            transform: rotate(0deg);
        }}

        to {{
            transform: rotate({target_angle}deg);
        }}

    }}

    </style>

    <div class="container">

        <div class="pointer"></div>

        <div class="wheel">
            {labels}
        </div>

        <div class="center"></div>

    </div>
    """

    components.html(
        html,
        height=460
    )


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

    st.write(
        "Selecciona qui està disponible avui."
    )

    selected_names = st.multiselect(
        "Disponibles:",
        [name for _, name in friends],
        default=[name for _, name in friends]
    )

    if len(selected_names) < 2:

        st.warning(
            "Selecciona almenys 2 persones."
        )

    else:

        selected_data = []

        for friend_id, name in friends:

            if name in selected_names:

                selected_data.append({
                    "id": friend_id,
                    "name": name,
                    "points": points[friend_id]
                })


        # ----------------------------------------------------
        # PESOS INVERSAMENT PROPORCIONALS
        # ----------------------------------------------------

        weights = []

        for person in selected_data:

            p = max(
                person["points"],
                0.1
            )

            weight = 1 / (
                p ** EXPONENT_RULETA
            )

            weights.append(weight)


        total_weight = sum(weights)


        # ----------------------------------------------------
        # PROBABILITATS
        # ----------------------------------------------------

        st.subheader("📊 Probabilitats")

        cols = st.columns(
            min(len(selected_data), 4)
        )

        for i, (person, weight) in enumerate(
            zip(selected_data, weights)
        ):

            probability = (
                weight /
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


        # ----------------------------------------------------
        # SORTEJAR
        # ----------------------------------------------------

        if st.button(
            "🎰 SORTEJAR",
            type="primary",
            use_container_width=True
        ):

            names = [
                person["name"]
                for person in selected_data
            ]

            winner = random.choices(
                names,
                weights=weights,
                k=1
            )[0]

            st.session_state["winner"] = winner

            st.session_state["show_wheel"] = True


        # ----------------------------------------------------
        # MOSTRAR RULETA
        # ----------------------------------------------------

        if st.session_state.get(
            "show_wheel",
            False
        ):

            winner = st.session_state["winner"]

            show_wheel(
                [
                    p["name"]
                    for p in selected_data
                ],
                winner
            )

            st.success(
                f"🚗 **{winner.upper()} FA COTXE!**"
            )

            if st.button(
                "🔄 Fer un altre sorteig"
            ):

                st.session_state.pop(
                    "winner",
                    None
                )

                st.session_state[
                    "show_wheel"
                ] = False

                st.rerun()


# ============================================================
# AFEGIR VIATGE
# ============================================================

with tab2:

    st.header("📝 Afegir viatge")

    st.write(
        "Aquí pots registrar qualsevol viatge."
    )

    names = [
        name
        for _, name in friends
    ]


    driver_name = st.selectbox(
        "🚗 Conductor:",
        names,
        key="driver_select"
    )


    passenger_options = [
        name
        for name in names
        if name != driver_name
    ]


    passenger_names = st.multiselect(
        "👥 Passatgers:",
        passenger_options,
        key="passenger_select"
    )


    col1, col2 = st.columns(2)

    with col1:

        party = st.checkbox(
            "🎉 Festa",
            key="party_check"
        )

    with col2:

        round_trip = st.checkbox(
            "🔄 Anada i tornada",
            key="round_trip_check"
        )


    trip_date = st.date_input(
        "📅 Data:",
        value=date.today(),
        key="date_select"
    )


    comment = st.text_area(
        "💬 Comentari (opcional):",
        placeholder="Ex: Festa de Girona",
        key="comment_input"
    )


    value = trip_value(
        len(passenger_names),
        party,
        round_trip
    )


    if passenger_names:

        loss_each = (
            value /
            len(passenger_names)
        )

        st.info(
            f"💰 {driver_name} guanyarà "
            f"**+{value:.1f} punts**.\n\n"
            f"Cada passatger perdrà "
            f"**-{loss_each:.1f} punts**."
        )

    else:

        st.warning(
            "Selecciona els passatgers."
        )


    # --------------------------------------------------------
    # BOTÓ QUE NOMÉS OBRE CONFIRMACIÓ
    # --------------------------------------------------------

    if st.button(
        "💾 CONTINUAR",
        type="primary",
        use_container_width=True
    ):

        if not passenger_names:

            st.error(
                "Has de seleccionar almenys un passatger."
            )

        else:

            st.session_state[
                "confirm_add_trip"
            ] = True


    # --------------------------------------------------------
    # MODAL DE CONFIRMACIÓ
    # --------------------------------------------------------

    if st.session_state.get(
        "confirm_add_trip",
        False
    ):

        @st.dialog("⚠️ Confirmar viatge")
        def confirm_add_dialog():

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
                    f"💬 **Comentari:** "
                    f"{comment.strip()}"
                )

            st.divider()

            loss_each = (
                value /
                len(passenger_names)
            )

            st.success(
                f"🚗 {driver_name}: "
                f"**+{value:.1f} punts**"
            )

            st.warning(
                f"👥 Cada passatger: "
                f"**-{loss_each:.1f} punts**"
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "❌ Cancel·lar",
                    use_container_width=True
                ):

                    st.session_state[
                        "confirm_add_trip"
                    ] = False

                    st.rerun()

            with col2:

                if st.button(
                    "✅ CONFIRMAR VIATGE",
                    type="primary",
                    use_container_width=True
                ):

                    driver_id = get_friend_id(
                        driver_name
                    )

                    passenger_ids = [
                        get_friend_id(name)
                        for name in passenger_names
                    ]

                    add_trip(
                        trip_date.strftime(
                            "%Y-%m-%d"
                        ),
                        driver_id,
                        passenger_ids,
                        round_trip,
                        party,
                        comment.strip()
                    )

                    st.session_state[
                        "confirm_add_trip"
                    ] = False

                    st.session_state[
                        "trip_added"
                    ] = True

                    st.rerun()


        confirm_add_dialog()


    # --------------------------------------------------------
    # CONFIRMACIÓ FINAL
    # --------------------------------------------------------

    if st.session_state.pop(
        "trip_added",
        False
    ):

        st.success(
            "✅ **VIATGE AFEGIT CORRECTAMENT!**"
        )

        st.toast(
            "Viatge afegit!",
            icon="🚗"
        )


# ============================================================
# CLASSIFICACIÓ
# ============================================================

with tab3:

    st.header("🏆 Classificació")

    stats = []

    for friend_id, name in friends:

        stats.append({
            "name": name,
            "points": points[friend_id]
        })


    stats.sort(
        key=lambda x: x["points"],
        reverse=True
    )


    for position, person in enumerate(stats):

        if position == 0:
            medal = "🥇"

        elif position == 1:
            medal = "🥈"

        elif position == 2:
            medal = "🥉"

        else:
            medal = f"{position + 1}."


        st.markdown(
            f"### {medal} {person['name']}"
        )

        st.write(
            f"**{person['points']:.1f} punts**"
        )

        progress = max(
            min(
                person["points"] / 200,
                1
            ),
            0
        )

        st.progress(progress)


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


    else:

        for trip in history:

            st.markdown(
                f"### 🚗 {trip['driver']} — "
                f"{trip['date']}"
            )


            if trip["passengers"]:

                st.write(
                    "👥 **Passatgers:** "
                    + ", ".join(
                        trip["passengers"]
                    )
                )

            else:

                st.write(
                    "👥 **Passatgers:** cap"
                )


            characteristics = []

            if trip["party"]:
                characteristics.append(
                    "🎉 Festa"
                )

            if trip["round_trip"]:
                characteristics.append(
                    "🔄 Anada i tornada"
                )


            if characteristics:

                st.write(
                    " · ".join(characteristics)
                )


            value = trip_value(
                len(trip["passengers"]),
                trip["party"],
                trip["round_trip"]
            )


            loss_each = (
                value /
                len(trip["passengers"])
                if trip["passengers"]
                else 0
            )


            st.write(
                f"💰 Conductor **+{value:.1f}** · "
                f"Passatgers **-{loss_each:.1f} cadascun**"
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
                key=f"delete_{trip['id']}"
            ):

                st.session_state[
                    "delete_trip_id"
                ] = trip["id"]

                st.rerun()


            # ------------------------------------------------
            # MODAL CONFIRMACIÓ ELIMINAR
            # ------------------------------------------------

            if st.session_state.get(
                "delete_trip_id"
            ) == trip["id"]:

                @st.dialog("⚠️ Eliminar viatge")
                def confirm_delete_dialog():

                    st.warning(
                        "Estàs segur que vols eliminar aquest viatge?"
                    )

                    st.write(
                        f"🚗 **Conductor:** "
                        f"{trip['driver']}"
                    )

                    st.write(
                        f"👥 **Passatgers:** "
                        f"{', '.join(trip['passengers'])}"
                    )

                    st.write(
                        "⚠️ Els punts es recalcularan "
                        "automàticament."
                    )

                    st.divider()

                    col1, col2 = st.columns(2)

                    with col1:

                        if st.button(
                            "❌ Cancel·lar",
                            use_container_width=True
                        ):

                            st.session_state.pop(
                                "delete_trip_id",
                                None
                            )

                            st.rerun()

                    with col2:

                        if st.button(
                            "🗑️ ELIMINAR",
                            type="primary",
                            use_container_width=True
                        ):

                            delete_trip(
                                trip["id"]
                            )

                            st.session_state.pop(
                                "delete_trip_id",
                                None
                            )

                            st.session_state[
                                "trip_deleted"
                            ] = True

                            st.rerun()


                confirm_delete_dialog()


            st.divider()


        if st.session_state.pop(
            "trip_deleted",
            False
        ):

            st.success(
                "✅ **VIATGE ELIMINAT!** "
                "Els punts s'han recalculat."
            )

            st.toast(
                "Viatge eliminat!",
                icon="🗑️"
            )