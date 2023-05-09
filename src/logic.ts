import { content } from "./content";
import { send } from "./send";
import { validate } from "./validate";
import { MyContext } from "./context";

const SKIP_MAX = 5;

function get_random_congrats(): string {
  return content.success[Math.floor(Math.random() * content.success.length)];
}

export const firstStep = async (ctx: MyContext) => {
  const stage = content.stages[0];
  await send(ctx, stage.messages || []);
  ctx.session.stage = 1;
};

export const stepProcessor = async (ctx: MyContext) => {
  if (ctx.message) {
    const text = "text" in ctx.message ? ctx.message.text : "";
    const stage = content.stages[ctx.session.stage];
    console.log(
      "MAIN_TEXT_PROCESSOR User: %d (%s) Stage: %s Message: %s",
      ctx.from?.id,
      ctx.from?.username,
      stage.name,
      text
    );
    if (stage.condition) {
      const user_answered = validate(text, stage.condition);
      const user_skiped = text.toLowerCase().includes("пропустить");
      const lives_left = SKIP_MAX - ctx.session.skip_counter;
      if (user_answered) {
        await send(ctx, [get_random_congrats()]);
      } else if (lives_left > 0 && user_skiped) {
        ctx.session.skip_counter++;
      } else {
        if (lives_left > 0) {
          await send(ctx, [
            {
              type: "text",
              text: content.try_again_text + lives_left,
              markup: ["Пропустить"],
            },
          ]);
        } else {
          await send(ctx, [content.wrong_answer_text]);
        }
        return;
      }
    }
    await send(ctx, stage.messages || []);
    // Set next state if possible
    if (ctx.session.stage < content.stages.length - 1) {
      ctx.session.stage++;
    }
    if (
      stage.name === "feedback" &&
      !validate(text, { type: "containsAny", values: ["идем", "дальше"] })
    ) {
      if (ctx.session.feedback) {
        ctx.session.feedback.push(text);
      } else {
        ctx.session.feedback = [text];
      }
    }
  }
};
