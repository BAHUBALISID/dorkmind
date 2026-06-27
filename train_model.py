import json
import pickle
import numpy as np
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout
from tensorflow.keras.utils import to_categorical
from pathlib import Path

# Paths
BASE_DORKS_PATH = "data/dorks_base.json"
TRAINING_DATA_PATH = "data/training_data.json"
MODEL_DIR = Path("data/model")
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "dork_model.h5"
TOKENIZER_PATH = MODEL_DIR / "tokenizer.pkl"

# Load base dorks
with open(BASE_DORKS_PATH, "r") as f:
    dorks_dict = json.load(f)
base_dorks = []
for cat in dorks_dict.values():
    base_dorks.extend(cat)

# Load training dorks (if any)
training_dorks = []
if Path(TRAINING_DATA_PATH).exists():
    with open(TRAINING_DATA_PATH, "r") as f:
        for line in f:
            try:
                rec = json.loads(line)
                training_dorks.append(rec["dork"])
            except:
                pass

# Combine all dorks
all_dorks = base_dorks + training_dorks
print(f"Total dorks: {len(all_dorks)} (base: {len(base_dorks)}, training: {len(training_dorks)})")

# Tokenization
tokenizer = Tokenizer(char_level=False, filters='', lower=True)
tokenizer.fit_on_texts(all_dorks)
total_words = len(tokenizer.word_index) + 1

# Create n-gram sequences
input_sequences = []
for dork in all_dorks:
    token_list = tokenizer.texts_to_sequences([dork])[0]
    for i in range(1, len(token_list)):
        n_gram_sequence = token_list[:i+1]
        input_sequences.append(n_gram_sequence)

max_len = max([len(x) for x in input_sequences])
input_sequences = pad_sequences(input_sequences, maxlen=max_len, padding='pre')
X, y = input_sequences[:,:-1], input_sequences[:,-1]
y = to_categorical(y, num_classes=total_words)

print(f"Sequence length: {max_len-1}, Vocab size: {total_words}")

# Build model
model = Sequential([
    Embedding(total_words, 64, input_length=max_len-1),
    LSTM(128),
    Dropout(0.2),
    Dense(total_words, activation='softmax')
])
model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

# Train
model.fit(X, y, epochs=10, batch_size=32, verbose=1)

# Save
model.save(str(MODEL_PATH))
with open(TOKENIZER_PATH, "wb") as f:
    pickle.dump(tokenizer, f)

print(f"Model saved to {MODEL_PATH}")
print(f"Tokenizer saved to {TOKENIZER_PATH}")
