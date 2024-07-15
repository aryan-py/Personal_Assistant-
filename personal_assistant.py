# -*- coding: utf-8 -*-
"""Personal_Assistant.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/17gY0-U5GdiZUiNW_bzvShIZ_xwD2Eb2D

# Create and run a local RAG pipeline from scratch

IMPORT PDF DOCUMENT
"""

import os
import requests


# Get PDF documents path
pdf_path ="human-nutrition-text.pdf"

# Download PDF
if not os.path.exists(pdf_path):
  print(f"[INFO] FIle doesn't exist, downloading ")

  # Enter the URL of the PDF
  url = "https://pressbooks.oer.hawaii.edu/humannutrition/open/download?type=pdf"

  # The local filename to save the downloaded file
  filename= pdf_path

  # Send GET request
  response = requests.get(url)

  # Check if th request was successful
  if response.status_code == 200:
    # Open the file in write mode
    with open(filename, "wb") as file:
      # Write the content of the response to the file
      file.write(response.content)

!pip install pymupdf
import fitz # requires pip install PyMuPDF, see https://github.com/PyMuPdf
from tqdm.auto import tqdm # pip install tqdm

def text_formatter(text: str) -> str:
  """Performs minor formatting on the text."""
  cleaned_text = text.replace("\n", " ").strip()

  #Potentially more text formating functions can go here
  return cleaned_text

def open_and_read(pdf_path: str) -> list[dict]:
  doc = fitz.open(pdf_path)
  pages_and_texts=[]
  for page_number, page in tqdm(enumerate(doc)):
    text=page.get_text()
    text = text_formatter(text=text)
    pages_and_texts.append({"page_number":page_number-41,
                           "page_char_count": len(text),
                           "page_word_count":len(text.split(" ")),
                           "page_sentece_count_raw":len(text.split(".")),
                           "page_token_count": len(text)/4, # 1 token = ~4 characters
                           "text":text})# because in the PDF the page number actually start after 41st page of the pdf.
  return pages_and_texts


pages_and_texts = open_and_read(pdf_path=pdf_path)
pages_and_texts[:2]

import pandas as pd
df = pd.DataFrame(pages_and_texts)
df.head()

df.describe().round(2)

from spacy.lang.en import English

nlp =English()

#Add a sentencizer pipeline, see https://spacy.io/api/sentencizer
nlp.add_pipe("sentencizer")

# Create document instance as an example
doc =nlp("This is a sentence. This is another sentence.")
assert len(list(doc.sents)) == 2

# Print out our sentences split
list(doc.sents)

for items in tqdm(pages_and_texts):
  items["sentences"]  = list(nlp(items["text"]).sents)

  # Make sure all sentences are strings (the default type is a spaCy datatype)
  items["sentences"] = [str(sentence) for sentence in items["sentences"]]

  # Count the sentences
  items["sentence_count"] = len(items["sentences"])

# Define split size to turn groups of sentences into chunks
num_sentence_chunk_size=10

#create a function to split lsits of text recursively into chunk size
def split_list(input_list: list, chunk_size: int=num_sentence_chunk_size) -> list[list[str]]:
  return [input_list [i:i+chunk_size] for i in range(0, len(input_list), chunk_size)]

# Loop through pages and text and split sentences into chunnks

for item in tqdm(pages_and_texts):
  item["sentences_chunks"] = split_list(input_list=item["sentences"],chunk_size=num_sentence_chunk_size)
  item["sentences_chunks_count"] = len(item["sentences_chunks"])

"""Splitting each chunk into it's own item

"""

import re

# Split each chunk into it's own item
pages_and_chunks =[]

for item in tqdm(pages_and_texts):
  for sentence_chunk in item["sentences_chunks"]:
    chunk_dict ={}
    chunk_dict["page_number"] = item["page_number"]

    # Join the sentences together into a pragraph like structure, aka join the list of sentences into one paragraph
    joined_sentence_chunk = " ".join(sentence_chunk).replace(" "," ").strip()
    joined_sentence_chunk = re.sub(r'\.([A-Z])', r'.\1',joined_sentence_chunk) # ".A" => ". A"(will work for any capital letter)

    chunk_dict["sentence_chunk"] = joined_sentence_chunk

    # Get some stats on our chunks
    chunk_dict["chunk_char_count"] = len(joined_sentence_chunk)
    chunk_dict["chunk_word_count"] = len([word for word in joined_sentence_chunk.split(" ")])
    chunk_dict["chunk_token_count"] = len(joined_sentence_chunk)/4 # 1 token =4chars

    pages_and_chunks.append(chunk_dict)

len(pages_and_chunks)

"""FILTER CHUNKS OF TEXT FOR CHORT CHUNKS

these chunks may not contain much useful information
"""

# Filter out DataFrame for rows with under 30 tokens
df=pd.DataFrame(pages_and_chunks)
min_tokens = 30
pages_and_chunks_over_min_tokens = df[df["chunk_token_count"]>min_tokens].to_dict(orient="records")

"""EMBEDDING OUR TEXT CHUNKS"""

!pip install sentence_transformers
from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer(model_name_or_path="all-mpnet-base-v2",device="cpu")

# Creating a list of sentences
sentences = ["The Sentence Transformer library provides an easy way to create embeddings",
             "Sentences can be embedded one by one or in a list.",
             "I like horses!"]

# Sentences are encoded/embedded by calling model.encode()
embeddings = embedding_model.encode(sentences)

embeddings_dict = dict(zip(sentences,embeddings))

# See the embeddings
for sentence, embedding in embeddings_dict.items():
  print(f"Sentence: {sentence}")
  print(f"Embedding: {embedding}")
  print("")

embeddings[0].shape

# Commented out IPython magic to ensure Python compatibility.
# %%time
# 
# embedding_model.to("cuda")
# 
# for item in tqdm(pages_and_chunks_over_min_tokens):
#   item["embedding"] = embedding_model.encode(item["sentence_chunk"])

# Commented out IPython magic to ensure Python compatibility.
# %%time
# 
# text_chunks =[item["sentence_chunk"] for item in pages_and_chunks_over_min_tokens]
# text_chunks[419]

len(text_chunks)

# Commented out IPython magic to ensure Python compatibility.
# %%time
# 
# #Embed all text in batches
# text_chunk_embeddings = embedding_model.encode(text_chunks, batch_size=32,# you can experiment to find which batch size leads to best result
#                                                convert_to_tensor=True)
# 
# text_chunk_embeddings

"""SAVE EMBEDDINGS TO FILE"""

# Save embeddings to file
text_chunk_embeddings_df=pd.DataFrame(pages_and_chunks_over_min_tokens)
embeddings_df_Save_path = "text_chunk_embeddings.csv"
text_chunk_embeddings_df.to_csv(embeddings_df_Save_path,index=False)

# Import saved file and view
text_chunk_embeddings_df_load = pd.read_csv(embeddings_df_Save_path)
text_chunk_embeddings_df_load.head()

import random

import torch
import numpy as np
import pandas as pd

device ="cuda" if torch.cuda.is_available() else "cpu"

# Imports texts and embedding off
text_chunk_embeddings_df = pd.read_csv("text_chunk_embeddings.csv")

#Convert embedding column back to np.array (it got converted to string when it saved to CSV)
text_chunk_embeddings_df["embedding"] = text_chunk_embeddings_df["embedding"].apply(lambda x: np.fromstring(x.strip("[]"), sep=" "))

# Convert our embeddings into a torch.tensor
embeddings = np.stack(text_chunk_embeddings_df["embedding"].tolist(), axis=0, dtype=torch.float32).to(device)
embeddings = torch.tensor(embeddings)

# Convert texts and embedding df to list of dicts
pages_and_chunks = text_chunk_embeddings_df.to_dict(orient="records")


text_chunk_embeddings_df

text_chunk_embeddings_df["embedding"]

embeddings = text_chunk_embeddings_df["embedding"].tolist()
embeddings

embeddings = np.stack(text_chunk_embeddings_df["embedding"].tolist(), axis=0)
embeddings

embeddings.shape

# Create model
from sentence_transformers import util
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer(model_name_or_path="all-mpnet-base-v2",device=device)

"""Note: to use dot product for comparison, ensure vector sizes are of same shape and tensors/vectors are in the same datatype"""

# 1. Define the query
query = "macronutrients functions"
printf(f" Query: {query}")

# 2. Embed the query
# Note: it's important to embed your quey with the same model you embedding your passages
query_embedding = embedding_model.encode(query, convert_to_tensor=True).to("cuda")

# 3. Get similarity scores with the dot product (use cosine similarity if outputs of model aren't normalized)
from time import perf_counter as timer

start_time = timer()
dot_scores = util.dot_score(a=query_embedding, b=embeddings)[0]
end_time = timer()

print(f"[INFO] Time taken to get scores on {len(embeddings)} embeddings: {end_time - start_time:.5f} seconds")

# 4. Get the top k resutls(we will keep top 5)
top_results_dot_product = torch.topk(dot_scores, k=5, dim=0)
top_results_dot_product

"""We can see that searching over embeddings is very fast even if we do exhaustive search.
But if you had 10M+ embeddings, you likely want to create an index.
An index is like letters in the dictionary.

"""

# Let's make our vector search results pretty.
import textwrap

def print_wrapped_text(text, wrap_length=80):
  wrapped_text = textwrap.fill(text, wrap_length)
  print(wrapped_text)

query = "macro nutrients functions"
print(f"Query: '{query}'\n")
print("Results:")
# loop through zipped together scores and indicesform torch.topk
for score, idx in zip(top_results_dot_product[0], top_results_dot_product[1]):
  print(f"Score:{score:.4f}")
  print("Text")
  print_wrapped(pages_and_chunks[idx]["sentence_chunk"])
  print(f"Page Number:{pages_and_chunks[idx]['page_number']}")
