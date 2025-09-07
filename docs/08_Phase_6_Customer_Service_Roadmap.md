# Roadmap: Customer Service Module Evolution

This document outlines a phased roadmap for evolving the Customer Service module from a simple message aggregator into an intelligent, autonomous agent.

### **V2: Foundational Enhancements & Scalability**

The goal of this phase is to move from the current prototype-level implementation to a robust, scalable architecture that can support real-time operations and future AI integrations.

**Step 1: Migrate Data Storage to a Relational Database (PostgreSQL)**
*   **Why:** The current JSON file storage is not suitable for production. It's not scalable, doesn't handle relationships well, and is not efficient for querying. PostgreSQL is a powerful, open-source, and self-hostable database perfect for this task.
*   **Action Plan:**
    1.  **Design Schema:** Create a database schema with tables for `threads`, `messages`, `customers`, and `orders`. Define foreign key relationships to link them (e.g., a message belongs to a thread, a thread is linked to an order).
    2.  **Setup PostgreSQL:** Deploy a self-hosted PostgreSQL instance.
    3.  **Update Application:** Modify the Python application to use a library like `SQLAlchemy` to connect to the new database. The `save_messages_to_json` function will be replaced with functions to insert/update records in the database.
    4.  **Data Migration:** Create a one-time script to migrate the historical data from `messages.json` into the new PostgreSQL database.

**Step 2: Implement Real-Time Message Ingestion with Webhooks & n8n**
*   **Why:** The current 15-minute polling is too slow for responsive customer service. The Mirakl platform supports webhooks, which enable real-time event-driven workflows. n8n is an excellent tool for orchestrating these workflows.
*   **Action Plan:**
    1.  **Configure Mirakl Webhook:** Set up a webhook in the Mirakl platform to trigger on "new customer message" events. This webhook will point to your self-hosted n8n instance.
    2.  **Create n8n Workflow:** Design an n8n workflow that catches the webhook from Mirakl.
    3.  **Create API Endpoint:** Build a new, simple API endpoint in the Python application (e.g., `/api/v1/new-message`).
    4.  **Connect n8n to App:** The n8n workflow will re-format the data from Mirakl if needed and then make an HTTP POST request to your new API endpoint to ingest the message in real-time.
    5.  **Deprecate Polling:** The original polling mechanism in the scheduler can be disabled, as messages will now arrive in real-time.

**Step 3: Develop a Basic Customer Service Dashboard**
*   **Why:** Human agents need a way to view and interact with the conversations. A simple web dashboard is essential for monitoring and manual intervention.
*   **Action Plan:**
    1.  **Choose Framework:** Use a lightweight Python web framework like **Flask** or **FastAPI**.
    2.  **Build UI:** Create a simple frontend that displays conversation threads retrieved from the PostgreSQL database. When a thread is selected, it should show all messages in chronological order and also display the linked order and shipping details.
    3.  **Enable Manual Replies:** Add a text box and a "Send" button to the dashboard, allowing a human agent to type a reply and send it via the Mirakl API.

---

### **V3: Intelligence and Automation**

With a solid foundation in place, this phase focuses on integrating LLMs to provide intelligent assistance and begin automating responses.

**Step 1: Implement a Retrieval-Augmented Generation (RAG) System**
*   **Why:** To provide accurate, context-aware answers, the LLM needs access to your internal knowledge base (e.g., return policies, product specs). RAG is the standard architecture for this.
*   **Action Plan:**
    1.  **Set up a Vector Database:** Deploy a vector database like **Weaviate** or use the `pgvector` extension for PostgreSQL. This will store your knowledge base as numerical representations.
    2.  **Curate Knowledge Base:** Gather all relevant documents: FAQs, shipping policies, return guidelines, product manuals, etc.
    3.  **Create Embedding Pipeline:** Write a script that chunks these documents, uses an embedding model (e.g., from OpenAI or a self-hosted model) to convert the text chunks into vectors, and stores them in the vector database.
    4.  **Integrate RAG:** When a new message arrives, the system will now perform this sequence:
        a.  Embed the customer's question into a vector.
        b.  Query the vector database to find the most relevant document chunks (the "context").
        c.  Pass the original question and the retrieved context to an LLM to generate a well-informed answer.

**Step 2: Build an "Intelligent Co-pilot" for Human Agents**
*   **Why:** Before allowing full automation, the LLM can act as a powerful assistant, drafting replies for human agents to review. This builds trust and allows for fine-tuning the AI's performance.
*   **Action Plan:**
    1.  **Add "Generate Draft" Button:** In the Customer Service Dashboard, add a button next to each incoming message labeled "Generate Draft Reply".
    2.  **Trigger RAG Workflow:** Clicking this button will execute the RAG workflow from the previous step.
    3.  **Display Draft:** The LLM-generated response will appear in the reply text box, where the human agent can review, edit, and then approve it to be sent.

**Step 3: Integrate with Internal Business Data APIs**
*   **Why:** To handle queries about inventory or make decisions about refunds, the system needs access to live business data.
*   **Action Plan:**
    1.  **Create Internal APIs:** Develop secure, internal-facing REST APIs that provide access to your inventory and cost/order databases.
    2.  **Give the LLM "Tools":** Use a modern LLM framework like LangChain or LlamaIndex to give the LLM access to "tools." These tools are functions that the LLM can decide to call.
    3.  **Implement Tools:** Write Python functions that call your new internal APIs (e.g., `check_inventory(product_id)`, `get_order_cost(order_id)`).
    4.  **Enable Tool Use:** Now, when a customer asks, "Is product X in stock?", the LLM can intelligently decide to call the `check_inventory` tool to get a live answer before formulating its response. Similarly, it can use cost data to calculate partial refunds based on your provided rules.

---

### **V4 and Beyond: Towards an Autonomous Agent**

This final phase focuses on enabling the system to handle common queries autonomously, freeing up your team to focus on high-value, complex issues.

**Step 1: Implement Intent Classification and Rule-Based Triage**
*   **Why:** Not all queries are created equal. The system needs to understand the customer's intent to decide whether it can handle the request itself or if it needs to escalate to a human.
*   **Action Plan:**
    1.  **Intent Classification:** Use an LLM to classify the intent of every new message (e.g., "order_status_inquiry," "return_request," "technical_support," "complaint").
    2.  **Confidence Scoring:** The LLM should also provide a confidence score for its classification.
    3.  **Routing Logic:** Create a routing engine. If the intent is simple (e.g., "order_status_inquiry") and the confidence is high (>95%), route it to the automated workflow. Otherwise, assign it to a human agent in the dashboard.

**Step 2: Full Automation for High-Confidence Workflows**
*   **Why:** This is the ultimate goal—to have the agent resolve common issues from start to finish without human intervention.
*   **Action Plan:**
    -   For the "order_status_inquiry" intent, the automated workflow would look like this:
        1.  Extract the order ID from the conversation context.
        2.  Call the internal shipping database to get the latest tracking status and link.
        3.  Generate a polite, helpful response for the customer.
        4.  Call the Mirakl API to send the response.
        5.  Automatically close the thread.
    -   Similar automated workflows can be built for other simple intents like "cancellation_request" (within a certain time window) or "address_update_request."

By following this phased approach, you can systematically build a powerful and intelligent customer service automation platform on the foundation we've already created.
