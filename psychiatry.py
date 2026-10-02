"""
Neo4j Psychiatry Clinical Analysis System - Streamlit Application
=================================================================
"""

import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import matplotlib.pyplot as plt
from streamlit_agraph import agraph, Node, Edge, Config

# ============================================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Psychiatry Clinical Network",
    layout="wide"
)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if 'driver' not in st.session_state:
    st.session_state.driver = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'database' not in st.session_state:
    st.session_state.database = None

# ============================================================================
# NEO4J CONNECTION FUNCTION
# ============================================================================
def connect_to_neo4j(uri, username, password, database=None):
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        session_kwargs = {"database": database} if database else {}
        with driver.session(**session_kwargs) as session:
            session.run("RETURN 1")
        return driver, True
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return None, False

# ============================================================================
# QUERY EXECUTION FUNCTION
# ============================================================================
def execute_query(query, parameters=None):
    if st.session_state.driver is None:
        return None
    try:
        session_kwargs = {"database": st.session_state.database} if st.session_state.database else {}
        with st.session_state.driver.session(**session_kwargs) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    except Exception as e:
        st.error(f"Query execution failed: {str(e)}")
        return None

# ============================================================================
# GRAPH VISUALIZATION ENGINE
# ============================================================================
def render_analytical_graph(query_type, results, selected_param=None):
    """Maps tabular data from analytical queries into visual graph nodes/edges."""
    nodes_dict = {}
    edges_list = []
    edge_set = set()

    def add_node(node_id, group):
        if not node_id or str(node_id) == "None": return
        if node_id not in nodes_dict:
            colors = {
                "Provider": "#97C2FC",    # Blue
                "Patient": "#FF9999",     # Red
                "Condition": "#DDA0DD",   # Purple
                "Symptom": "#FFCC99",     # Orange
                "Medication": "#99FF99"   # Green
            }
            nodes_dict[node_id] = Node(id=node_id, label=node_id, size=25, color=colors.get(group, "#CCCCCC"))

    def add_edge(source, target, label):
        if not source or not target or str(source) == "None" or str(target) == "None": return
        edge_id = f"{source}_{target}_{label}"
        if edge_id not in edge_set:
            edges_list.append(Edge(source=source, target=target, label=label, type="CURVE_SMOOTH"))
            edge_set.add(edge_id)

    # Process rules based on which query was run
    for row in results:
        if query_type == "Patients by Provider":
            pr = selected_param
            p = row.get("patient_name")
            c = row.get("condition")
            rel = row.get("care_type", "TREATS")

            add_node(pr, "Provider")
            add_node(p, "Patient")
            add_node(c, "Condition")

            add_edge(pr, p, rel)
            if c: add_edge(p, c, "DIAGNOSED_WITH")

        elif query_type == "High-Risk Roster":
            p = row.get("patient")
            c = row.get("condition")
            pr = row.get("care_provider")
            m = row.get("current_med")

            add_node(p, "Patient")
            add_node(c, "Condition")
            add_node(pr, "Provider")
            add_node(m, "Medication")

            if c: add_edge(p, c, "DIAGNOSED_WITH")
            if pr: add_edge(pr, p, "TREATS")
            if pr and m: add_edge(pr, m, "PRESCRIBES")

        elif query_type == "Comorbidity Analysis (Shared Symptoms)":
            c1 = selected_param
            c2 = row.get("overlapping_condition")
            s = row.get("overlapping_symptom")

            add_node(c1, "Condition")
            add_node(c2, "Condition")
            add_node(s, "Symptom")

            add_edge(c1, s, "HAS_SYMPTOM")
            add_edge(c2, s, "HAS_SYMPTOM")

        elif query_type == "Differential Diagnosis (Patients with Similar Profiles)":
            p1 = selected_param
            p2 = row.get("similar_patient")
            s = row.get("shared_symptom")
            c = row.get("their_diagnosis")

            add_node(p1, "Patient")
            add_node(p2, "Patient")
            add_node(s, "Symptom")
            add_node(c, "Condition")

            add_edge(p1, s, "EXHIBITS")
            add_edge(p2, s, "EXHIBITS")
            if c: add_edge(p2, c, "DIAGNOSED_WITH")

        elif query_type == "Medication Usage by Condition":
            c = selected_param
            m = row.get("medication")
            pr = row.get("prescribing_doctor")
            p = row.get("patient_treated")

            add_node(c, "Condition")
            add_node(m, "Medication")
            add_node(pr, "Provider")
            add_node(p, "Patient")

            add_edge(p, c, "DIAGNOSED_WITH")
            add_edge(pr, p, "TREATS")
            add_edge(pr, m, "PRESCRIBES")

    if not nodes_dict:
        st.warning("No connections found to graph.")
        return

    config = Config(width="100%", height=600, directed=True, physics=True, hierarchical=False)
    return agraph(nodes=list(nodes_dict.values()), edges=edges_list, config=config)


# Generic graph parser for Custom Cypher query
def display_interactive_graph(results):
    if not results: return
    nodes, edges, processed_ids = [], [], set()

    for record in results:
        for key, value in record.items():
            if isinstance(value, dict) and 'name' in value:  
                node_id = value.get('name') 
                color = "#97C2FC" 
                if 'risk_level' in value: color = "#FF9999" 
                elif 'class' in value: color = "#99FF99" 
                elif 'description' in value: color = "#FFCC99" 
                if node_id not in processed_ids:
                    nodes.append(Node(id=node_id, label=node_id, size=25, color=color))
                    processed_ids.add(node_id)
            elif isinstance(value, dict) and 'condition' in key.lower() and 'name' in value:
                 node_id = value.get('name')
                 if node_id not in processed_ids:
                    nodes.append(Node(id=node_id, label=node_id, size=25, color="#DDA0DD"))
                    processed_ids.add(node_id)

    for record in results:
        values = list(record.values())
        if len(values) >= 3: 
            source_dict = values[0] if isinstance(values[0], dict) else {}
            target_dict = values[2] if isinstance(values[2], dict) else {}
            source_id = source_dict.get('name') if source_dict else str(values[0])
            target_id = target_dict.get('name') if target_dict else str(values[2])
            rel_type = str(values[1])
            if source_id in processed_ids and target_id in processed_ids:
                edges.append(Edge(source=source_id, target=target_id, label=rel_type, type="CURVE_SMOOTH"))

    config = Config(width="100%", height=600, directed=True, physics=True, hierarchical=False)
    return agraph(nodes=nodes, edges=edges, config=config)

# ============================================================================
# SIDEBAR & CONNECTION
# ============================================================================
st.sidebar.title("Neo4j Connection")
st.sidebar.markdown("Enter your Neo4j database credentials")

uri = st.sidebar.text_input("URI", value="bolt://localhost:7687")
username = st.sidebar.text_input("Username", value="neo4j")
password = st.sidebar.text_input("Password", type="password")
database = st.sidebar.text_input("Database Name", value="")

if st.sidebar.button("Connect"):
    with st.spinner("Connecting..."):
        db_name = database.strip() if database.strip() else None
        st.session_state.database = db_name
        driver, connected = connect_to_neo4j(uri, username, password, db_name)
        if connected:
            st.session_state.driver = driver
            st.session_state.connected = True
            st.sidebar.success(f"Connected to '{db_name if db_name else 'default'}'!")
        else:
            st.session_state.connected = False

if st.sidebar.button("Disconnect"):
    if st.session_state.driver:
        st.session_state.driver.close()
        st.session_state.driver = None
        st.session_state.connected = False
        st.sidebar.info("Disconnected")

# ============================================================================
# MAIN CONTENT AREA
# ============================================================================
st.title("Psychiatry Clinical Network Analysis")
st.markdown("Explore patient networks, comorbidities, and symptom overlaps using graph data.")

if not st.session_state.connected:
    st.info("Please connect to your Neo4j database using the sidebar to get started.")
    st.stop()

query_type = st.selectbox(
    "Select Clinical Analysis Type",
    [
        "Database Overview",
        "Patients by Provider",
        "High-Risk Roster",
        "Comorbidity Analysis (Shared Symptoms)",
        "Differential Diagnosis (Patients with Similar Profiles)",
        "Medication Usage by Condition",
        "Interactive Patient Dashboard",
        "Custom Cypher Query"
    ]
)

# ============================================================================
# ROUTING QUERIES
# ============================================================================
if query_type == "Database Overview":
    st.header("Database Statistics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Nodes")
        node_query = "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
        st.code(node_query, language="cypher")
        if res := execute_query(node_query):
            st.dataframe(pd.DataFrame(res), use_container_width=True)
            
    with col2:
        st.subheader("Relationships")
        rel_query = "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count"
        st.code(rel_query, language="cypher")
        if res := execute_query(rel_query):
            st.dataframe(pd.DataFrame(res), use_container_width=True)
            
    with col3:
        st.subheader("Sample Patients")
        sample_query = "MATCH (p:Patient) RETURN p.name as name, p.age as age, p.risk_level as risk LIMIT 10"
        st.code(sample_query, language="cypher")
        if res := execute_query(sample_query):
            st.dataframe(pd.DataFrame(res), use_container_width=True)

elif query_type == "Patients by Provider":
    st.header("Provider Caseload & Patient Overview")
    if providers := execute_query("MATCH (pr:Provider) RETURN DISTINCT pr.name as provider ORDER BY pr.name"):
        selected_provider = st.selectbox("Select a Provider", [p['provider'] for p in providers])
        if selected_provider:
            query = """
            MATCH (pr:Provider {name: $provider_name})-[r:TREATS|COUNSELS]->(p:Patient)
            OPTIONAL MATCH (p)-[:DIAGNOSED_WITH]->(c:Condition)
            RETURN p.name as patient_name, p.risk_level as risk_level, type(r) as care_type, c.name as condition
            ORDER BY risk_level DESC, patient_name
            """
            st.markdown("**Executed Cypher Query:**")
            st.code(query, language="cypher")
            
            results = execute_query(query, {"provider_name": selected_provider})
            if results:
                view = st.radio("View Mode", ["Graph Network", "Data Table"], horizontal=True, key="pbp")
                if view == "Graph Network":
                    render_analytical_graph(query_type, results, selected_provider)
                else:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

elif query_type == "High-Risk Roster":
    st.header("High-Risk Patient Action List")
    query = """
    MATCH (p:Patient {risk_level: 'High'})
    OPTIONAL MATCH (p)-[:DIAGNOSED_WITH]->(c:Condition)
    OPTIONAL MATCH (pr:Provider)-[:TREATS|COUNSELS]->(p)
    OPTIONAL MATCH (pr)-[:PRESCRIBES]->(m:Medication)
    RETURN p.name as patient, c.name as condition, pr.name as care_provider, m.name as current_med
    """
    st.markdown("**Executed Cypher Query:**")
    st.code(query, language="cypher")
    
    results = execute_query(query)
    if results:
        view = st.radio("View Mode", ["Graph Network", "Data Table"], horizontal=True, key="hrr")
        if view == "Graph Network":
            render_analytical_graph(query_type, results)
        else:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.success("No high-risk patients found.")

elif query_type == "Comorbidity Analysis (Shared Symptoms)":
    st.header("Condition Comorbidity via Shared Symptoms")
    if conditions := execute_query("MATCH (c:Condition) RETURN DISTINCT c.name as condition ORDER BY condition"):
        selected_condition = st.selectbox("Select Target Condition", [c['condition'] for c in conditions])
        if selected_condition:
            query = """
            MATCH (c1:Condition {name: $condition})<-[:DIAGNOSED_WITH]-(p1:Patient)-[:EXHIBITS]->(s:Symptom)<-[:EXHIBITS]-(p2:Patient)-[:DIAGNOSED_WITH]->(c2:Condition)
            WHERE c1 <> c2
            RETURN DISTINCT c2.name as overlapping_condition, s.description as overlapping_symptom
            """
            st.markdown("**Executed Cypher Query:**")
            st.code(query, language="cypher")
            
            results = execute_query(query, {"condition": selected_condition})
            if results:
                view = st.radio("View Mode", ["Graph Network", "Data Table"], horizontal=True, key="cas")
                if view == "Graph Network":
                    render_analytical_graph(query_type, results, selected_condition)
                else:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

elif query_type == "Differential Diagnosis (Patients with Similar Profiles)":
    st.header("Patient Symptom Clustering")
    if patients := execute_query("MATCH (p:Patient) RETURN DISTINCT p.name as patient ORDER BY patient"):
        selected_patient = st.selectbox("Select Patient Case", [p['patient'] for p in patients])
        if selected_patient:
            query = """
            MATCH (p1:Patient {name: $patient_name})-[:EXHIBITS]->(s:Symptom)<-[:EXHIBITS]-(p2:Patient)
            WHERE p1 <> p2
            OPTIONAL MATCH (p2)-[:DIAGNOSED_WITH]->(c:Condition)
            RETURN DISTINCT p2.name as similar_patient, s.description as shared_symptom, c.name as their_diagnosis
            """
            st.markdown("**Executed Cypher Query:**")
            st.code(query, language="cypher")
            
            results = execute_query(query, {"patient_name": selected_patient})
            if results:
                view = st.radio("View Mode", ["Graph Network", "Data Table"], horizontal=True, key="dd")
                if view == "Graph Network":
                    render_analytical_graph(query_type, results, selected_patient)
                else:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

elif query_type == "Medication Usage by Condition":
    st.header("Medication Efficacy & Usage Network")
    if conditions := execute_query("MATCH (c:Condition) RETURN DISTINCT c.name as condition ORDER BY condition"):
        selected_condition = st.selectbox("Select Condition", [c['condition'] for c in conditions])
        if selected_condition:
            query = """
            MATCH (c:Condition {name: $condition})<-[:DIAGNOSED_WITH]-(p:Patient)<-[:TREATS]-(pr:Provider)-[:PRESCRIBES]->(m:Medication)
            RETURN DISTINCT m.name as medication, pr.name as prescribing_doctor, p.name as patient_treated
            """
            st.markdown("**Executed Cypher Query:**")
            st.code(query, language="cypher")
            
            results = execute_query(query, {"condition": selected_condition})
            if results:
                view = st.radio("View Mode", ["Graph Network", "Data Table"], horizontal=True, key="muc")
                if view == "Graph Network":
                    render_analytical_graph(query_type, results, selected_condition)
                else:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

elif query_type == "Interactive Patient Dashboard":
    st.header("Interactive Patient Scatter Plot")
    query = """
    MATCH (p:Patient)
    OPTIONAL MATCH (p)-[:DIAGNOSED_WITH]->(c:Condition)
    OPTIONAL MATCH (p)-[:EXHIBITS]->(s:Symptom)
    RETURN p.name AS Name, p.age AS Age, p.risk_level AS Risk_Level, c.name AS Condition, count(s) AS Symptoms
    """
    st.markdown("**Underlying Cypher Query:**")
    st.code(query, language="cypher")
    
    if results := execute_query(query):
        df = pd.DataFrame(results).fillna({'Condition': 'None', 'Risk_Level': 'Unknown'})
        
        st.sidebar.title("Dashboard Filters")
        choice_condition = st.sidebar.selectbox("Select Condition:", df['Condition'].unique())
        choice_risk = st.sidebar.radio("Select Risk Level", df['Risk_Level'].unique().tolist() or ["Low", "High"])
        min_age, max_age = int(df['Age'].min()) if not df['Age'].empty else 18, int(df['Age'].max()) if not df['Age'].empty else 80
        choice_age = st.sidebar.slider("Minimum Age:", min_age, max_age if max_age > min_age else min_age + 1, min_age)
        choice_symptoms = st.sidebar.number_input("Minimum Symptoms:", 0, 20, 1)
        
        df_result = df[(df['Condition'] == choice_condition) & (df['Risk_Level'] == choice_risk) & (df['Age'] >= choice_age) & (df['Symptoms'] >= choice_symptoms)]
        
        if not df_result.empty:
            fig, ax = plt.subplots()
            ax.scatter(df_result['Age'], df_result['Symptoms'], color='teal', alpha=0.7)
            ax.set_xlabel('Patient Age'); ax.set_ylabel('Total Symptoms'); ax.set_title(f"Symptom Distribution for {choice_risk} Risk {choice_condition} Patients")
            st.pyplot(fig)
        else:
            st.warning("No patients match.")

elif query_type == "Custom Cypher Query":
    st.header("Execute Custom Cypher Query")
    query = st.text_area("Cypher Query", value="MATCH (p:Patient)-[r:EXHIBITS]->(s:Symptom)\nRETURN p, type(r) as relationship, s\nLIMIT 15", height=200)
    view_toggle = st.radio("View", ["Graph Network", "Data Table"], horizontal=True, key="custom")
    if st.button("Execute Query", type="primary") and query.strip():
        with st.spinner("Executing..."):
            if results := execute_query(query):
                if view_toggle == "Graph Network":
                    display_interactive_graph(results)
                else:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

st.markdown("---")
st.markdown("**Psychiatry Clinical Analysis System** | Built with Streamlit")