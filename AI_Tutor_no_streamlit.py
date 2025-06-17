import openai
from openai import OpenAI
import os
import random
from collections import deque
import time

# Nastav svůj OpenAI klíč
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai.api_key)

# Stav
score_window = deque(maxlen=10)
asked_questions = set()

# OpenAI dotaz
def ask_openai(prompt, system_msg="You are a helpful assistant."):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

# Vyhodnocení odpovědi
def evaluate_answer(q_type, user_answer, correct_answer):
    if q_type == "is_correct":
        user_answer = user_answer.strip().upper()
        correct_answer = correct_answer.strip().upper()
        correct_answer = correct_answer.strip(".,!?")
        is_correct = user_answer == correct_answer
        return is_correct, ''

    prompt = (
        f"Žák napsal větu: '{user_answer}' a správná věta zní: '{correct_answer}'. "
        "Porovnej tyto dvě věty. Odpověz nejprve pouze 'ANO' (pokud žákova věta je gramaticky i významově správná) nebo 'NE' (pokud ne). "
        "Poté vysvětli, proč je odpověď správná nebo chybná. Neodpovídej na žádnou otázku obsaženou ve větách."
    )
    response = ask_openai(
        prompt,
        system_msg="Posuzuj gramatiku a význam věty, zejména v rámci časů Present Simple a Present Continuous. "
                "Neodpovídej na žádné otázky ve větách. Nejprve napiš jen 'ANO' nebo 'NE', pak vysvětli proč."
    )

    words = response.strip().split()
    first_word = words[0].upper().strip(".,!?")

    if first_word not in ["ANO", "NE"]:
        for word in words:
            clean_word = word.upper().strip(".,!?")
            if clean_word in ["ANO", "NE"]:
                first_word = clean_word
                break
        else:
            return False, f"(⚠️ Nešlo určit ANO/NE) {response.strip()}"

    is_correct = first_word == "ANO"
    return is_correct, response.strip()

# Generátor otázek
def generate_question():
    question_types = ["translate", "is_correct", "fix_sentence"]
    sentence_types = ["afirmativní", "negativní", "tázací"]
    grammar_tenses = ["Present Simple", "Present Continuous"]

    for _ in range(5):
        q_type = random.choice(question_types)
        # q_type = "translate"
        tense = random.choice(grammar_tenses)
        s_type = random.choice(sentence_types)

        if q_type == "translate":
            cz = ask_openai(f"Vymysli jednoduchou českou větu pro test gramatiky {tense}. Jen větu.")
            en = ask_openai(f"Přelož do angličtiny: '{cz}'")
            if cz in asked_questions:
                continue
            asked_questions.add(cz)
            return ("translate", cz, en, '')

        elif q_type == "is_correct":
            text = ask_openai(
                f"Vymysli krátkou anglickou {s_type} větu v {tense}, která je buď správná nebo chybná. "
                "Vrať výstup ve formátu:\n"
                "Věta=... (anglická věta)\n"
                "Odpověď=ANO nebo NE (zda je věta správně)\n"
                "Správně=... (správná verze věty, jen pokud byla chybná; jinak tuto část vynech)"
            )
            
            if all(keyword in text for keyword in ["Věta=", "Odpověď="]):
                parts = text.split("Věta=")[-1].split("Odpověď=")
                sentence = parts[0].strip()
                remainder = parts[1]

                # Získání odpovědi a případné správné věty
                if "Správně=" in remainder:
                    correct, correction = remainder.split("Správně=")
                    correct = correct.strip().upper()
                    correction = correction.strip()
                else:
                    correct = remainder.strip().upper()
                    correction = sentence  # pokud je správná, neměním

                if sentence in asked_questions:
                    continue

                asked_questions.add(sentence)
                return ("is_correct", sentence, correct, correction)

        elif q_type == "fix_sentence":
            text = ask_openai(f"Napiš anglickou {s_type} větu v {tense} s chybou. Vrať: wrong=..., correct=...")
            if "wrong=" in text and "correct=" in text:
                parts = text.split("wrong=")[-1].split("correct=")
                wrong = parts[0].strip()
                correct = parts[1].strip()
                if wrong in asked_questions:
                    continue
                asked_questions.add(wrong)
                return ("fix_sentence", wrong, correct, '')
    return None

# Hlavní cyklus
def main():
    print("🎓 Procvičování angličtiny: Present Simple vs Continuous")
    print("🧠 Cvičení překladu, oprav chyb a rozpoznání správnosti vět.")
    print("Zadej odpověď a potvrď Enter. Pro ukončení stiskni Ctrl+C.")
    print("-" * 60)

    while True:
        question_data = generate_question()
        if not question_data:
            print("⚠️ Nepodařilo se vytvořit otázku. Zkuste znovu.")
            continue

        q_type, question, correct, correction = question_data

        if q_type == "translate":
            print(f"➡️ Přelož do angličtiny: '{question}'")
            user = input("✏️ Tvoje odpověď: ")

        elif q_type == "is_correct":
            print(f"➡️ Je tato věta správně? '{question}'")
            user = input("✏️ Odpověz 'ANO' nebo 'NE': ")

        elif q_type == "fix_sentence":
            print(f"➡️ Oprav chybnou větu: '{question}'")
            user = input("✏️ Napiš správně: ")

        # Vyhodnocení
        is_correct, feedback = evaluate_answer(q_type, user, correct)

        if is_correct:
            print("✅ Správně!")
            if q_type != "is_correct":
                print(f"ℹ️ Vysvětlení: {feedback}")
            else:
                print(f"ℹ️ Správná věta: {correction}")  
            score_window.append(1)
        else:
            print(f"❌ Špatně. Správně mělo být: {correct}")
            if q_type != "is_correct":
                print(f"ℹ️ Vysvětlení: {feedback}")
            else:
                print(f"ℹ️ Správná věta: {correction}")      
            score_window.append(0)

        # Zobrazení skóre
        score_percent = int((sum(score_window) / len(score_window)) * 100)
        print(f"📊 Tvoje skóre za posledních {len(score_window)} odpovědí: {score_percent}%")
        print("-" * 60)

        # Gratulace při 10 správných odpovědích
        if len(score_window) == 10 and all(v == 1 for v in score_window):
            print("🏆 Gratuluji! Máš 10 správných odpovědí po sobě! 🎉")
            break

        time.sleep(1)

if __name__ == "__main__":
    main()
