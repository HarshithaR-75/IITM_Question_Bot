import OpenAI from "openai";

const openai = new OpenAI({
    apiKey: "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", // Replace with your actual OpenAI API key
});

const completion = await openai.chat.completions.create({
    model: "gpt-3.5-turbo",
    messages: [
        { role: "system", content: "You are a helpful assistant." },
        {
            role: "user",
            content: "Write a haiku about recursion in programming.",
        },
    ],
});

console.log(completion.choices[0].message);
