from typing import List, Dict, Optional
from ollama import Client
from apps.config.settings import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.llm.url
        self.model = settings.llm.model
        self.max_history = settings.llm.max_history_msgs
        self.temperature = settings.llm.conversation_temperature
        self.max_tokens = settings.llm.max_tokens

        print(f"[OllamaClient] Ollama URL: {self.base_url}")
        print(f"[OllamaClient] Model: {self.model}")

        self.client = Client(host=self.base_url)

    def generate_response(
            self,
            messages: List[Dict[str, str]],
            temperature: Optional[float] = None
    ) -> str:
        """
        Generate a response using Ollama

        Args:
            messages: Conversation history
            temperature: Override default temperature (optional)
        """
        try:
            # Limit conversation history to avoid context overflow
            limited_messages = messages[-self.max_history:]

            print(f"[OllamaClient] Sending {len(limited_messages)} messages:")
            for i, msg in enumerate(limited_messages):
                print(f"  [{i}] role={msg.get('role')}, content={msg.get('content')[:60]}...")

            # Clean messages: Remove timestamp field
            clean_messages = []
            for msg in limited_messages:
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                clean_messages.append(clean_msg)

            # Use override temperature or default
            temp = temperature if temperature is not None else self.temperature
            print(f"[OllamaClient] Calling Ollama (temp={temp}) with {len(clean_messages)} messages")

            # Pass temperature to Ollama
            response = self.client.chat(
                model=self.model,
                messages=clean_messages,
                options={
                    "temperature": temp,
                    "num_predict": self.max_tokens  # Max tokens to generate
                }
            )

            reply = response['message']['content']
            print(f"[OllamaClient] Got reply: {reply[:80]}...")
            return reply

        except Exception as e:
            # Fallback response if Ollama fails
            return f"I'm having trouble connecting to my AI model: {str(e)}"

    # ← NEW: Add async generate() method for single-string prompts
    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response from a single prompt (async version)

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Generated text response
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Use generate_response (which is sync) but wrap it
        # Note: Since generate_response is sync, we just call it directly
        return self.generate_response(messages, temperature=temperature)


# Global instance
ollama_client = OllamaClient()