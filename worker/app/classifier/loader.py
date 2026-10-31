# Load the two-head classifier written by training/notebooks/classifier_training.ipynb.
# Read it from /app/models (the ./models mount).
# classifier.keras is the shared BiLSTM, with a category head and a priority head.
# word2idx.json and text_prep.json repeat the notebook's vocabulary and cleaning.
# category_labels.json and priority_labels.json are the softmax index order.
# Expose a model version or file identity that trace.py can store.
# Loading this file needs TensorFlow, the same library the notebook used to save it.
