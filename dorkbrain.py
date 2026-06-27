import json
import pickle
import numpy as np
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences

class DorkBrain:
    def __init__(self, model_path=None):
        self.tokenizer = None
        self.model = None
        self.max_len = 40
        if model_path:
            self.load(model_path)

    def prepare_data(self, dorks_list):
        if not self.tokenizer:
            self.tokenizer = Tokenizer(char_level=False, filters='', lower=True)
            self.tokenizer.fit_on_texts(dorks_list)
        sequences = []
        for dork in dorks_list:
            seq = self.tokenizer.texts_to_sequences([dork])[0]
            sequences.append(seq)
        max_len = max(len(s) for s in sequences) if sequences else 1
        self.max_len = max_len
        X, y = [], []
        for seq in sequences:
            for i in range(1, len(seq)):
                X.append(seq[:i])
                y.append(seq[i])
        X = pad_sequences(X, maxlen=max_len, padding='pre')
        y = np.array(y)
        return X, y, max_len

    def build_model(self, vocab_size, max_len):
        model = Sequential([
            Embedding(vocab_size, 64, input_length=max_len),
            LSTM(128, return_sequences=False),
            Dropout(0.2),
            Dense(vocab_size, activation='softmax')
        ])
        model.compile(loss='sparse_categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
        self.model = model
        self.max_len = max_len

    def train(self, dorks_list, epochs=5, batch_size=32):
        X, y, max_len = self.prepare_data(dorks_list)
        if not self.model:
            self.build_model(len(self.tokenizer.word_index) + 1, max_len)
        self.model.fit(X, y, epochs=epochs, batch_size=batch_size, verbose=1)

    def generate_dork(self, seed="intitle:index of", num_words=15, temperature=0.8):
        if not self.model or not self.tokenizer:
            return seed
        for _ in range(num_words):
            seq = self.tokenizer.texts_to_sequences([seed])[0]
            seq = pad_sequences([seq], maxlen=self.max_len, padding='pre')
            preds = self.model.predict(seq, verbose=0)[0]
            preds = np.log(preds + 1e-7) / temperature
            exp_preds = np.exp(preds)
            preds = exp_preds / np.sum(exp_preds)
            next_idx = np.random.choice(len(preds), p=preds)
            if next_idx == 0:
                break
            for word, idx in self.tokenizer.word_index.items():
                if idx == next_idx:
                    seed += ' ' + word
                    break
        return seed

    def reinforcement_feedback(self, good_dorks, epochs=2):
        self.train(good_dorks, epochs=epochs)

    def save(self, path):
        self.model.save(f"{path}/dork_model.h5")
        with open(f"{path}/tokenizer.pkl", "wb") as f:
            pickle.dump(self.tokenizer, f)

    def load(self, path):
        self.model = load_model(f"{path}/dork_model.h5")
        with open(f"{path}/tokenizer.pkl", "rb") as f:
            self.tokenizer = pickle.load(f)
