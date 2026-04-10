import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class QuizManager:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            print("Warning: GROQ_API_KEY not found in .env")
        
        # Initialize Groq client only if key is available
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        
        # Store materials collected from the owner.
        # Format: { course_id: { week_index: "material text" } }
        self.course_materials = {}

    def save_material(self, course_id, week_index, text):
        """Save text material for a specific course and week."""
        if course_id not in self.course_materials:
            self.course_materials[course_id] = {}
        self.course_materials[course_id][week_index] = text
        print(f"Saved material for course {course_id}, week {week_index}. Length: {len(text)}")

    def get_material(self, course_id, week_index, fallback_text=None):
        """Retrieve stored material, or return fallback."""
        if course_id in self.course_materials and week_index in self.course_materials[course_id]:
            return self.course_materials[course_id][week_index]
        return fallback_text

    def generate_weekly_quiz(self, material_text):
        """
        Uses Groq to generate a 5-question multiple choice quiz based on the material.
        Returns a list of dictionaries, each containing:
        { "question": str, "options": [str, str, str, str], "correct_index": int (0-3) }
        """
        if not self.client:
            print("Error: Groq client not initialized")
            return []

        system_prompt = """
        You are a helpful educational assistant creating a quiz for students based on their weekly course material.
        Given the following text from the course material, generate exactly 5 multiple-choice questions.
        Each question must have exactly 4 options.
        Output your response ONLY as a valid JSON array of objects. Do not include any markdown formatting like ```json or any conversational text.
        
        Example exact format required:
        [
            {
                "question": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "correct_index": 2
            }
        ]
        """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Here is the weekly material. Please generate the quiz.\n\nMaterial:\n{material_text}"
                    }
                ],
                model="llama-3.1-8b-instant", # Fast and capable enough for JSON generation
                temperature=0.3,
                max_tokens=2000,
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Clean up potential markdown formatting if the model disobeys instructions
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            response_text = response_text.strip()
            
            quiz_data = json.loads(response_text)
            
            # Validate output structure
            if not isinstance(quiz_data, list) or len(quiz_data) != 5:
                print(f"Warning: Quiz generation returned {len(quiz_data) if isinstance(quiz_data, list) else 'non-list'} items instead of 5.")
                
            return quiz_data
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse Groq response into JSON: {e}")
            print(f"Raw response: {response_text}")
            return []
        except Exception as e:
             print(f"Error generating quiz with Groq: {e}")
             return []

    def generate_practice_question(self, material_text):
        """
        Uses Groq to generate a single multiple choice practice question based on the material.
        Returns a single dictionary:
        { "question": str, "options": [str, str, str, str], "correct_index": int (0-3) }
        """
        if not self.client:
            print("Error: Groq client not initialized")
            return None

        system_prompt = """
        You are a helpful educational assistant creating a single practice question for a student based on their weekly course material.
        Given the following text from the course material, generate ONE multiple-choice question.
        The question must have exactly 4 options.
        Output your response ONLY as a valid JSON object. Do not include any markdown formatting like ```json or any conversational text.
        
        Example exact format required:
        {
            "question": "What is the capital of France?",
            "options": ["London", "Berlin", "Paris", "Madrid"],
            "correct_index": 2
        }
        """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Here is the weekly material. Please generate one practice question.\n\nMaterial:\n{material_text}"
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0.5, # Slightly higher temperature for variety in practice questions
                max_tokens=500,
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Clean up potential markdown formatting
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            response_text = response_text.strip()
            
            question_data = json.loads(response_text)
            
            if not isinstance(question_data, dict) or "question" not in question_data:
                 print(f"Warning: Practice question generation returned unexpected format.")
                 return None
                 
            return question_data
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse Groq response into JSON (Practice Question): {e}")
            print(f"Raw response: {response_text}")
            return None
        except Exception as e:
             print(f"Error generating practice question with Groq: {e}")
             return None

    def answer_question(self, question: str, material_text: str) -> str:
        """
        Uses Groq to answer a student's question based on the weekly material.
        Returns the answer as a string.
        """
        if not self.client:
            print("Error: Groq client not initialized")
            return "I am currently unable to answer questions because my AI is not connected."

        system_prompt = """
        You are a helpful and encouraging educational assistant for a course. 
        A student is asking a question. Please answer their question using ONLY the provided course material.
        If the answer cannot be found in the provided material, politely inform them that the material does not cover this topic 
        and suggest they ask the instructor or check other resources. Do not use outside knowledge.
        Keep your answer concise, clear, and directly address the student's question.
        """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Course Material:\n{material_text}\n\nStudent's Question: {question}"
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0.3,
                max_tokens=1000,
            )
            
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error answering question with Groq: {e}")
            return "Sorry, I ran into an error trying to interpret that question. Please try again later."


if __name__ == '__main__':
    # Test script for QuizManager
    print("Testing QuizManager...")
    qm = QuizManager()
    
    test_material = "Photosynthesis is a process used by plants and other organisms to convert light energy into chemical energy that, through cellular respiration, can later be released to fuel the organism's activities. This chemical energy is stored in carbohydrate molecules, such as sugars and starches, which are synthesized from carbon dioxide and water – hence the name photosynthesis, from the Greek phōs, 'light', and sunthesis, 'putting together'. In most cases, oxygen is also released as a waste product."
    
    print("\n--- Generating 5-Question Quiz ---")
    quiz = qm.generate_weekly_quiz(test_material)
    if quiz:
        for i, q in enumerate(quiz):
            print(f"\nQ{i+1}: {q.get('question')}")
            for j, opt in enumerate(q.get('options', [])):
                prefix = '*' if j == q.get('correct_index') else ' '
                print(f" {prefix} {chr(65+j)}. {opt}")
    
    print("\n--- Generating Single Practice Question ---")
    practice_q = qm.generate_practice_question(test_material)
    if practice_q:
         print(f"Q: {practice_q.get('question')}")
         for j, opt in enumerate(practice_q.get('options', [])):
            prefix = '*' if j == practice_q.get('correct_index') else ' '
            print(f" {prefix} {chr(65+j)}. {opt}")
