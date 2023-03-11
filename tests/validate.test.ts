import { expect } from "chai";
import { validate } from "../src/validate";

describe("Validation tests", () => {
  it("containsAny must be case insensitive", () => {
    expect(
      validate("Hello, world!", {
        type: "containsAny",
        values: ["hello"],
      })
    ).to.be.true;
  });
  it("containsAny with extra words", () => {
    expect(
      validate("Hello, world!", {
        type: "containsAny",
        values: ["missing", "hello", "world"],
      })
    ).to.be.true;
  });
  it("containsAny fail", () => {
    expect(
      validate("Hello, world!", {
        type: "containsAny",
        values: ["missing"],
      })
    ).to.be.false;
  });
});
