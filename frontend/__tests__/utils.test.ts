import { describe, expect, it } from "vitest";
import { cn } from "@/lib/utils";

describe("cn", () => {
  it("merges tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});
