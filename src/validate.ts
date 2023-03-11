import { Condition } from "./content";

function containsAny(text: string, values: string[]) {
  const formatted = text.toLowerCase();
  for (let val of values) {
    if (formatted.includes(val.toLowerCase())) {
      return true;
    }
  }
  return false;
}

export function validate(text: string, condition: Condition) {
  switch (condition.type) {
    case "containsAny":
      return containsAny(text, condition.values);
  }
}
