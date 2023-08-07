import { Context } from "telegraf";

export interface MyContext extends Context {
  session: {
    skip_counter: number;
    stage: number;
    startedAt: string;
  };
}

export function initialState() {
  return { skip_counter: 0, stage: 0, startedAt: new Date().toJSON() };
}
