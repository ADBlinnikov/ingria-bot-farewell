import fs from "fs";
import { parse } from "yaml";
import { Message } from "./send";

export type Condition = {
  type: "containsAny" | "containsAll";
  values: string[];
};
export type Stage = {
  name: string;
  messages?: Message[];
  condition?: Condition;
  markup?: string[];
};
export type Content = {
  get_going_text: string;
  wrong_answer_text: string;
  try_again_text: string;
  success: string[];
  stages: Stage[];
};

// Read excursion text
const file = fs.readFileSync("./text.yaml", "utf8");
export const content = parse(file) as Content;

content.stages.forEach((stage, idx) => {
  if (stage.name === undefined)
    throw new Error("No name specified for stage " + idx);
  if (stage.messages === undefined)
    throw new Error("No messages specified for stage " + stage.name);
});
