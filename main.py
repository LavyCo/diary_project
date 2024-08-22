
from flask import Flask, render_template, request, jsonify
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from crewai import Agent
import random
import re

app = Flask(__name__)

# Initialize the LLM model
llm = OllamaLLM(model="llama3")

# Initialize the agents correctly
game_agent = Agent(
    role="Game Agent",
    goal="Create fun and educational word games to help kids learn English.",
    backstory="""
    You are a game designer who loves helping kids learn.
    You create word games that are easy and fun to play.
    """,
    llm=llm
)

english_teaching_agent = Agent(
    role="English Teaching Agent",
    goal="Help kids practice English through daily conversations.",
    backstory="""
    You are a friendly English teacher who loves chatting with kids.
    You help them improve their English by talking about their day.
    If the user you are talking to makes a grammar or spelling mistake, you correct them.
    Show only the incorrect words and their corrections.
    """,
    llm=llm
)

vocabulary_agent = Agent(
    role="Vocabulary Agent",
    goal="Provide accurate and simple definitions for English words.",
    backstory="""
    You are a vocabulary expert who helps kids learn the meaning of words.
    You provide clear, concise, and child-friendly definitions.
    """,
    llm=llm
)

chatbot_agent = Agent(
    role="Chatbot Agent",
    goal="Help the child choose what to do and make sure they have fun learning.",
    backstory="""
    You are a friendly guide who helps kids choose between playing a game or learning English.
    You make sure the child is having a fun and educational experience.
    """,
    llm=llm
)

# Global list to store corrected words for the game
corrected_words = []

# List to track the full conversation with corrections
conversation_log = []


# Function to correct sentences and detect spelling mistakes using the understanding of the English Teaching Agent
def correct_sentence_using_agent(sentence):
    correction_prompt = ChatPromptTemplate.from_template(
        """You are a friendly English teacher. The user will provide a sentence, and you need to correct any spelling mistakes.
           Format your response as follows:
           Corrected sentence: <corrected sentence>
           Mistakes: "incorrect_word" should be "correct_word"

           Sentence: {input}
           AI:"""
    )
    correction_chain = correction_prompt | english_teaching_agent.llm
    correction_response = correction_chain.invoke({"input": sentence}).strip()

    # Extract the corrected sentence and corrections from the response
    corrected_sentence_match = re.search(r'Corrected sentence: (.+)', correction_response)
    corrections_matches = re.findall(r'"(.+)" should be "(.+)"', correction_response)

    corrected_sentence = corrected_sentence_match.group(1) if corrected_sentence_match else sentence
    corrections = [{"original_word": w, "corrected_word": c} for w, c in corrections_matches]

    return corrected_sentence, corrections


# Task to track corrections without disrupting the conversation
def background_correction_task(text):
    corrected_sentence, corrections = correct_sentence_using_agent(text)
    for correction in corrections:
        if correction['corrected_word'] not in corrected_words:
            corrected_words.append(correction['corrected_word'])

    # Log the original and corrected sentences
    conversation_log.append({
        "original": text,
        "corrected": corrected_sentence,
        "corrections": corrections
    })


# Function to handle the conversation with the child
@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    if user_input:
        # Check if the user is ending the conversation
        if user_input.strip().lower() == "goodbye":
            summary = "Here is a summary of your conversation:\n"
            for entry in conversation_log:
                summary += f"\nOriginal: {entry['original']}\nCorrected: {entry['corrected']}\n"
                if entry['corrections']:
                    summary += "Corrections:\n"
                    for correction in entry['corrections']:
                        summary += f"- \"{correction['original_word']}\" should be \"{correction['corrected_word']}\"\n"
            # Clear the conversation log after summary is presented
            conversation_log.clear()
            return jsonify({"response": summary})

        # Keep the conversation natural with the child
        english_prompt = ChatPromptTemplate.from_template(
            """You are a friendly English teacher. Engage in a conversation with the child about their day.
               Don't correct them directly in the conversation. Just keep the chat going naturally.

               User: {input}
               AI:"""
        )
        english_chain = english_prompt | english_teaching_agent.llm
        ai_response = english_chain.invoke({"input": user_input}).strip()

        # Perform background correction task
        background_correction_task(user_input)

        return jsonify({"response": ai_response})

    return jsonify({"response": "I didn't catch that, could you say it again?"})


# Function to generate simple and short meanings for a given word
def generate_meanings(word, model):
    """Generate simple and short meanings for a given word."""
    prompt = ChatPromptTemplate.from_template(
        f"Provide a very short and simple meaning of the word '{word}' suitable for a child. Keep it under 5 words."
    )
    meaning_chain = prompt | model
    correct_meaning = meaning_chain.invoke({"input": word}).strip()

    # Generate similar but incorrect simple meanings
    meanings = [correct_meaning]
    while len(meanings) < 4:
        additional_meaning_prompt = ChatPromptTemplate.from_template(
            f"Provide a plausible but incorrect meaning for the word '{word}' that is simple and could trick a child learning the language. Keep it under 5 words."
        )
        additional_meaning_chain = additional_meaning_prompt | model
        additional_meaning = additional_meaning_chain.invoke({"input": word}).strip()
        meanings.append(additional_meaning)

    random.shuffle(meanings)
    correct_index = meanings.index(correct_meaning)

    return correct_index, meanings


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/conversation')
def conversation():
    return render_template('conversation.html')


@app.route('/game')
def game():
    return render_template('game.html')


@app.route('/next_question', methods=['POST'])
def next_question():
    if corrected_words:
        word_to_test = corrected_words.pop(0)  # Use the first corrected word
    else:
        word_to_test = random.choice(["apple", "banana", "orange", "grape", "pineapple"])

    correct_index, meanings = generate_meanings(word_to_test, vocabulary_agent.llm)
    return jsonify({
        "question": f"What is the correct meaning of the word '{word_to_test}'?",
        "options": meanings,
        "correct_index": correct_index
    })


@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.json
    selected_index = data.get('selected_index')
    correct_index = data.get('correct_index')

    if selected_index == correct_index:
        return jsonify({"result": "Correct", "next": True})
    else:
        return jsonify({"result": "Incorrect", "next": False})


if __name__ == "__main__":
    app.run(debug=True)



