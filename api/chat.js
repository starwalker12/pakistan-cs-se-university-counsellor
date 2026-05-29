/*
 * Serverless API route for Vercel deployment
 * 
 * This function runs on Vercel's server (not in the browser).
 * It receives the user's question and FAQ context from the frontend,
 * builds a prompt, and sends it to OpenRouter API.
 * 
 * Why a serverless function?
 * - API keys must never be in frontend code
 * - The serverless function keeps OPENROUTER_API_KEY secret
 * - Only the serverless function talks to OpenRouter
 * - The browser only talks to our own serverless function
 */

// If OPENROUTER_MODEL env var is not set, use this default
const DEFAULT_MODEL = 'openai/gpt-4o-mini';

module.exports = async (req, res) => {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ reply: 'Only POST requests are allowed.' });
  }

  // Extract user message and FAQ context from request body
  const { userMessage, faqContext } = req.body;

  // Validate that userMessage exists
  if (!userMessage) {
    return res.status(400).json({ reply: 'No user message provided.' });
  }

  // Get API key from environment variables (set in Vercel dashboard)
  const apiKey = process.env.OPENROUTER_API_KEY;

  // If no API key is set, return a clear error without crashing
  if (!apiKey) {
    console.error('OPENROUTER_API_KEY is not set in environment variables.');
    return res.status(200).json({
      reply: 'The AI service is not configured yet. Please contact the administrator.'
    });
  }

  // Determine which model to use
  const model = process.env.OPENROUTER_MODEL || DEFAULT_MODEL;

  // Build the system prompt
  let systemPrompt = 'You are a helpful university admission assistant.';
  systemPrompt += ' Answer in simple and clear English.';
  systemPrompt += ' Keep the answer short.';
  systemPrompt += ' Do not use markdown. Do not use bold text. Do not use asterisks or stars.';
  systemPrompt += ' Use simple numbered steps if needed.';

  // If FAQ context is available, include it in the system prompt
  let userPrompt = '';
  if (faqContext) {
    userPrompt += 'Useful FAQ information:\n';
    userPrompt += 'Question: ' + faqContext.question + '\n';
    userPrompt += 'Answer: ' + faqContext.answer + '\n\n';
  }
  userPrompt += 'User question: ' + userMessage;

  try {
    // Call OpenRouter chat completions API
    // OpenRouter uses the same format as OpenAI's API
    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + apiKey,
        'HTTP-Referer': 'https://university-admission-chatbot.vercel.app',
        'X-Title': 'University Admission Chatbot'
      },
      body: JSON.stringify({
        model: model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ]
      })
    });

    // If OpenRouter returned an error, log it and return fallback
    if (!response.ok) {
      const errorText = await response.text();
      console.error('OpenRouter error:', response.status, errorText);
      return res.status(200).json({
        reply: 'The AI service is temporarily unavailable. Please try again later.'
      });
    }

    // Parse the response and extract the AI's reply
    const data = await response.json();
    const reply = data.choices[0].message.content.trim();

    // Return the AI reply to the frontend
    return res.status(200).json({ reply: reply });

  } catch (error) {
    // If any error occurs (network, timeout, etc.), log and return fallback
    console.error('OpenRouter request failed:', error.message);
    return res.status(200).json({
      reply: 'The AI service is temporarily unavailable. Please try again later.'
    });
  }
};
