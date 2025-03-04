import os
import streamlit as st
from crewai import Agent, Task, Crew, Process
from crewai_tools import QdrantVectorSearchTool
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize Qdrant vector search tool
qdrant_tool = QdrantVectorSearchTool(
    qdrant_url=os.getenv("QDRANT_URL"),
    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
    collection_name="legal_documents_collection",
    limit=3,
    score_threshold=0.50
)

### **1️⃣ Query Agent: Fetches Relevant Legal Documents** ###
query_agent = Agent(
    role="Legal Query Agent",
    goal="Fetch the most relevant legal sections based on user queries.",
    backstory="You are a legal research expert, skilled in retrieving precise legal information.",
    tools=[qdrant_tool],
    base_model="gpt-4o-mini",
    verbose=True
)

# **Query Task: Retrieves Legal Documents**
query_task = Task(
    description="""Find the most relevant legal documents for the given query.
    Extract key sections related to the topic and present them in a structured format:
    - Title of the legal section
    - Key points
    - Relevance score
    - Source of the document
    """,
    agent=query_agent,
    expected_output="A structured list of legal documents, each with title, key points, and relevance score."
)

### **2️⃣ Summarization Agent: Converts Results into Clear Answers** ###
summarization_agent = Agent(
    role="Legal Summarization Agent",
    goal="Summarize legal documents into clear, structured, and easy-to-understand answers.",
    backstory="You are a legal expert, skilled at simplifying complex legal texts while maintaining accuracy.",
    base_model="gpt-4o-mini",
    verbose=True
)

# **Summarization Task: Converts Search Results into User-Friendly Response**
summarization_task = Task(
    description="""Summarize the retrieved legal documents into a clear, concise response.
    Structure the response as:
    - **Brief Explanation**: A summary of the legal concept.
    - **Step-wise Breakdown and simplification of the answer to the query** (if applicable).
    - **Legal References**: Source and key sections.
    - **Clarification Option**: Ask if the user needs more details.
    """,
    agent=summarization_agent,
    expected_output="A well-structured legal response with clear explanations, step-wise breakdown, and references."
)


# **Streamlit UI Setup**
st.set_page_config(page_title="Legal AI Assistant", layout="wide")
st.title("⚖️ Legal AI Assistant")
st.write("Enter a legal query, and our AI-powered assistant will retrieve and summarize relevant legal information.")

# User Input
user_query = st.text_input("Enter your legal question:", "")

if st.button("Get Answer"):
    if user_query:
        # Display progress
        progress_bar = st.progress(0)
        st.write("🔍 Searching legal database...")

        # **Step 1: Query Agent Execution**
        crew = Crew(
            agents=[query_agent],
            tasks=[query_task],
            process=Process.sequential,
            verbose=True,
        )
        query_result = crew.kickoff(inputs={"query": user_query})

        # ✅ Extract the response content properly
        if isinstance(query_result, dict):
            extracted_query_result = query_result.get("output", "")  # Extracts the output string if in a dictionary
        else:
            extracted_query_result = str(query_result)  # Converts to string if not a dictionary

        # Update progress
        progress_bar.progress(50)
        st.write("📖 Retrieving relevant legal sections...")

        # **Step 2: Summarization Agent Execution**
        crew = Crew(
            agents=[summarization_agent],
            tasks=[summarization_task],
            process=Process.sequential,
            verbose=True,
        )
        final_result = crew.kickoff(inputs={"query": extracted_query_result})  # ✅ Pass extracted result

        # Clear previous messages
        st.empty()
        progress_bar.progress(100)

        # **Final Output**
        st.success("✅ Here’s the summarized legal information:")
        st.markdown(final_result)
