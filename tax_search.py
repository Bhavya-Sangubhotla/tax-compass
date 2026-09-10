from google.cloud import bigquery


PROJECT_ID = "tax-data-project-506117"
DATASET_ID = "taxdata"
TABLE_ID = "tax_documents"
MODEL_ID = "tax_embedding_model"


def search_tax_documents(question: str, top_k: int = 5) -> str:
    """
    Search the tax document knowledge base using semantic vector search.

    Args:
        question: The user's tax-related question.
        top_k: Number of relevant document chunks/pages to return.

    Returns:
        Relevant document content formatted as text for the agent.
    """

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT
        base.document_name,
        base.page_number,
        base.content,
        distance
    FROM VECTOR_SEARCH(
        TABLE `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`,
        'embedding',
        (
            SELECT
                ml_generate_embedding_result AS embedding
            FROM ML.GENERATE_EMBEDDING(
                MODEL `{PROJECT_ID}.{DATASET_ID}.{MODEL_ID}`,
                (
                    SELECT @question AS content
                ),
                STRUCT(TRUE AS flatten_json_output)
            )
        ),
        top_k => @top_k,
        distance_type => 'COSINE'
    )
    ORDER BY distance
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "question",
                "STRING",
                question
            ),
            bigquery.ScalarQueryParameter(
                "top_k",
                "INT64",
                top_k
            ),
        ]
    )

    print("🔎 [RAG] search_tax_documents CALLED", flush=True)
    print(f"🔎 [RAG] Query: {question}", flush=True)

    query_job = client.query(
        query,
        job_config=job_config
    )

    results = query_job.result()

    formatted_results = []

    for row in results:
        formatted_results.append(
            f"""
Document: {row.document_name}
Page: {row.page_number}
Relevance distance: {row.distance}

Content:
{row.content}
"""
        )

    if not formatted_results:
        return "No relevant information was found in the tax documents."
    
    print(f"📚 [RAG] Retrieved {len(formatted_results)} chunks", flush=True)
    return "\n\n---\n\n".join(formatted_results)


# question = "Who is eligible to file ITR-1?"

# results = search_tax_documents(question)

# print(results)