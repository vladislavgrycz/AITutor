import os, time, random
from collections import deque
from openai import OpenAI

# ——————————————————————————————————————————————————————————————
# Konfigurace OpenAI klienta
# ——————————————————————————————————————————————————————————————
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

def ask_openai(prompt: str, system_msg: str) -> str:
    """Obalovací funkce pro systémový a uživatelský prompt."""
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system",  "content": system_msg},
            {"role": "user",    "content": prompt}
        ],
        temperature=0.5
    )
    return resp.choices[0].message.content.strip()


# ——————————————————————————————————————————————————————————————
# Generování otázek
# ——————————————————————————————————————————————————————————————
asked_questions = set()

def generate_question() -> tuple[str,str,str,str] | None:
    """Vytvoří novou otázku:
       - translate: (translate, cz, en, "")
       - is_correct: (is_correct, sentence, ANO/NE, correct_sentence)
       - fix_sentence: (fix_sentence, wrong_sentence, correct_sentence, "")
    """
    types   = ["translate", "is_correct", "fix_sentence"]
    forms   = ["afirmativní", "negativní", "tázací"]
    tenses  = ["Present Simple", "Present Continuous"]

    for _ in range(5):
        q_type   = random.choice(types)
        form     = random.choice(forms)
        tense    = random.choice(tenses)

        if q_type == "translate":
            cz = ask_openai(
                f"Vymysli jednu jednoduchou českou větu k procvičení {tense}.",
                system_msg="Vrať pouze tu větu."
            )
            en = ask_openai(
                f"Přelož do angličtiny přesně tuto větu: „{cz}“.",
                system_msg="Vrať pouze překlad, bez dalších komentářů."
            )
            if cz not in asked_questions:
                asked_questions.add(cz)
                return ("translate", cz, en, "")

        elif q_type == "is_correct":
            text = ask_openai(
                f"Vymysli krátkou anglickou {form} větu v čase {tense}. Některé věty"
                " musí být gramaticky správné, jiné s chybou. "
                "Vypiš výstup **přesně** takto (bez uvozovek):\n"
                "Věta=<ta věta>\n"
                "Odpověď=ANO nebo NE\n"
                "Správně=<správná verze věty, pouze pokud byla Odpověď=NE>\n",
                system_msg=(
                    "Přísně dodrž formát. Nepiš nic navíc. "
                    "Nesnaž se odpovědět na otázku obsaženou ve větě."
                )
            )
            # Robustní parsování
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            data = { line.split("=",1)[0]: line.split("=",1)[1] for line in lines if "=" in line }
            if "Věta" in data and "Odpověď" in data:
                sent    = data["Věta"]
                answer  = data["Odpověď"].upper().strip()
                corr    = data.get("Správně", sent)
                if sent not in asked_questions:
                    asked_questions.add(sent)
                    return ("is_correct", sent, answer, corr)

        else:  # fix_sentence
            text = ask_openai(
                f"Napiš anglickou {form} větu v čase {tense} s gramatickou chybou. "
                "Pak vypiš správnou verzi. Formát:\n"
                "wrong=<chybná>\n"
                "correct=<správná>\n",
                system_msg="Přísně dodrž formát. Nepis nic navíc."
            )
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            data = { line.split("=",1)[0]: line.split("=",1)[1] for line in lines if "=" in line }
            if "wrong" in data and "correct" in data:
                wrong = data["wrong"]
                corr  = data["correct"]
                if wrong not in asked_questions:
                    asked_questions.add(wrong)
                    return ("fix_sentence", wrong, corr, "")

    return None


# ——————————————————————————————————————————————————————————————
# Vyhodnocení odpovědi
# ——————————————————————————————————————————————————————————————
def evaluate_answer(q_type: str, user: str, correct: str) -> tuple[bool,str]:
    """Vrátí (je_správně, zpětná_vazba)."""
    if q_type == "is_correct":
        # jednoduché porovnání ANO/NE bez OpenAI
        return user.strip().upper() == correct, ""
    # pro ostatní případy původní prompt
    prompt = (
        f"Žák přeložil nebo opravil: '{user}'. Správně je: '{correct}'.\n"
        "Porovnej tyto dvě věty. Nejprve napiš **pouze** 'ANO' pokud je shoda, "
        "nebo 'NE' pokud ne. Pak stručně vysvětli, proč."
    )
    fb = ask_openai(
        prompt,
        system_msg=(
            "Vyhodnocuj pouze gramatiku Present Simple/Continuous a sémantiku. "
            "Neodpovídej na žádnou otázku obsaženou ve větách."
        )
    )
    first = fb.strip().split()[0].upper().strip(".,!?")
    if first not in ("ANO","NE"):
        first = "NE"
        fb = "(⚠️ Přečteno jako NE) " + fb
    return (first=="ANO"), fb


# ——————————————————————————————————————————————————————————————
# Hlavní smyčka v konzoli
# ——————————————————————————————————————————————————————————————
def main():
    score = deque(maxlen=10)
    print("Procvičování: Present Simple vs Continuous\n")
    while True:
        q = generate_question()
        if not q:
            print("⚠️ Nelze vygenerovat otázku, zkus znovu.")
            continue

        q_type, q_text, correct, correction = q
        if q_type == "translate":
            print(f"Přelož: '{q_text}'")
            user = input("> ")
        elif q_type == "is_correct":
            print(f"Je tato věta správně(Ano/Ne)? '{q_text}'")
            user = input("> ")
        else:
            print(f"Oprav chybu: '{q_text}'")
            user = input("> ")

        ok, fb = evaluate_answer(q_type, user, correct)
        if ok:
            print("✅ Správně!")
            print(f"ℹ️ Správně mělo znít: {correct}")
         
            if q_type=="is_correct":
                print(f"ℹ️ Správná věta: {correction}")
            else:           
                print(f"ℹ️ {fb}")
            score.append(1)
        else:
            print("❌ Špatně.")
            print(f"Správně mělo být: {correct}")
            if q_type=="is_correct":
                print(f"ℹ️ Správná věta: {correction}")
            else:
                print(f"ℹ️ {fb}")
            score.append(0)

        pct = int(sum(score)/len(score)*100)
        print(f"Skóre (posl. {len(score)}): {pct}%")
        print("-"*40)

        if len(score) == 10 and sum(score) >= 9:
            print(f"🎉 Gratuluji! Výborný výsledek: {sum(score)}/10 správně! 🎉")
            break
        time.sleep(1)


if __name__=="__main__":
    main()
