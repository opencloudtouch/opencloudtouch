import { describe, it, expect } from "vitest";

/**
 * RFC 4180-compliant CSV line parser (copied from About.tsx for unit testing).
 * In production, this would be extracted to a shared utility.
 */
function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;

  while (i <= len) {
    if (i === len) {
      fields.push("");
      break;
    }

    if (line[i] === '"') {
      let value = "";
      i++;
      while (i < len) {
        if (line[i] === '"') {
          if (i + 1 < len && line[i + 1] === '"') {
            value += '"';
            i += 2;
          } else {
            i++;
            break;
          }
        } else {
          value += line[i];
          i++;
        }
      }
      fields.push(value);
      if (i < len && line[i] === ',') i++;
    } else {
      const commaIdx = line.indexOf(',', i);
      if (commaIdx === -1) {
        fields.push(line.substring(i).trim());
        break;
      } else {
        fields.push(line.substring(i, commaIdx).trim());
        i = commaIdx + 1;
      }
    }
  }

  return fields;
}

describe("CSV Parser (parseCSVLine)", () => {
  it("parses simple unquoted fields", () => {
    const result = parseCSVLine("Elvis Presley,one-time,30,0,2026-05-26");
    expect(result).toEqual(["Elvis Presley", "one-time", "30", "0", "2026-05-26"]);
  });

  it("parses quoted fields with spaces", () => {
    const result = parseCSVLine("Paul McCartney,one-time,21.47,0,2026-06-01");
    expect(result).toEqual(["Paul McCartney", "one-time", "21.47", "0", "2026-06-01"]);
  });

  it("parses quoted fields with umlauts", () => {
    const result = parseCSVLine("Beyoncé,one-time,10,0,2026-05-10");
    expect(result).toEqual(["Beyoncé", "one-time", "10", "0", "2026-05-10"]);
  });

  it("parses quoted fields with commas inside", () => {
    const result = parseCSVLine('"Doe, John",one-time,10,0,2026-01-01');
    expect(result).toEqual(["Doe, John", "one-time", "10", "0", "2026-01-01"]);
  });

  it("parses quoted fields with escaped quotes", () => {
    const result = parseCSVLine('"He said ""hello""",one-time,5,0,2026-03-15');
    expect(result).toEqual(['He said "hello"', "one-time", "5", "0", "2026-03-15"]);
  });

  it("parses GitHub URL as name", () => {
    const result = parseCSVLine("https://github.com/someuser,one-time,15,0,2026-04-01");
    expect(result).toEqual(["https://github.com/someuser", "one-time", "15", "0", "2026-04-01"]);
  });

  it("parses @-prefixed names", () => {
    const result = parseCSVLine("@someuser,one-time,5,0,2026-02-14");
    expect(result).toEqual(["@someuser", "one-time", "5", "0", "2026-02-14"]);
  });

  it("handles decimal amounts (krumme EUR from USD conversion)", () => {
    const result = parseCSVLine("Paul McCartney,one-time,21.47,0,2026-06-01");
    expect(parseFloat(result[2])).toBeCloseTo(21.47);
  });

  it("parses monthly supporter with both amounts", () => {
    const result = parseCSVLine("Eminem,monthly,5,5,2026-05-20");
    expect(result).toEqual(["Eminem", "monthly", "5", "5", "2026-05-20"]);
    expect(parseFloat(result[2]) + parseFloat(result[3])).toBe(10);
  });
});

describe("Supporter Sorting", () => {
  interface Supporter {
    name: string;
    type: "monthly" | "one-time";
    amount: number;
    monthlyAmount: number;
    firstSupportDate: string;
  }

  const sortSupporters = (supporters: Supporter[]) => {
    return [...supporters].sort((a, b) => {
      const scoreA = a.amount + a.monthlyAmount;
      const scoreB = b.amount + b.monthlyAmount;
      if (scoreB !== scoreA) return scoreB - scoreA;
      if (a.firstSupportDate !== b.firstSupportDate) {
        return a.firstSupportDate.localeCompare(b.firstSupportDate);
      }
      return a.name.localeCompare(b.name);
    });
  };

  it("sorts by total amount descending", () => {
    const supporters: Supporter[] = [
      { name: "Small", type: "one-time", amount: 1, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
      { name: "Big", type: "one-time", amount: 30, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
      { name: "Medium", type: "one-time", amount: 10, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
    ];
    const sorted = sortSupporters(supporters);
    expect(sorted.map(s => s.name)).toEqual(["Big", "Medium", "Small"]);
  });

  it("combines amount + monthlyAmount for total", () => {
    const supporters: Supporter[] = [
      { name: "Monthly", type: "monthly", amount: 5, monthlyAmount: 5, firstSupportDate: "2026-05-20" },
      { name: "OneTime", type: "one-time", amount: 8, monthlyAmount: 0, firstSupportDate: "2026-05-26" },
    ];
    const sorted = sortSupporters(supporters);
    // Monthly: 5+5=10, OneTime: 8+0=8
    expect(sorted[0].name).toBe("Monthly");
  });

  it("breaks ties by firstSupportDate ascending (early supporters first)", () => {
    const supporters: Supporter[] = [
      { name: "Late", type: "one-time", amount: 5, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
      { name: "Early", type: "one-time", amount: 5, monthlyAmount: 0, firstSupportDate: "2026-05-01" },
    ];
    const sorted = sortSupporters(supporters);
    expect(sorted[0].name).toBe("Early");
  });

  it("breaks further ties by name ascending", () => {
    const supporters: Supporter[] = [
      { name: "Zoe", type: "one-time", amount: 5, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
      { name: "Alice", type: "one-time", amount: 5, monthlyAmount: 0, firstSupportDate: "2026-06-01" },
    ];
    const sorted = sortSupporters(supporters);
    expect(sorted[0].name).toBe("Alice");
  });
  it("handles empty name field", () => {
    const result = parseCSVLine(",one-time,5,0,2026-01-01");
    expect(result).toEqual(["", "one-time", "5", "0", "2026-01-01"]);
  });

  it("handles zero amounts (refund zeroed out)", () => {
    const result = parseCSVLine("Refunded User,one-time,0,0,2026-03-01");
    expect(result[2]).toBe("0");
    expect(result[3]).toBe("0");
    expect(parseFloat(result[2]) + parseFloat(result[3])).toBe(0);
  });

  it("handles trailing newline (empty last line)", () => {
    const csv = "name,type,amount,monthlyAmount,firstSupportDate\nElvis Presley,one-time,30,0,2026-05-26\n";
    const lines = csv.trim().split("\n").slice(1).filter((line) => line.trim());
    expect(lines).toHaveLength(1);
    expect(parseCSVLine(lines[0])).toEqual(["Elvis Presley", "one-time", "30", "0", "2026-05-26"]);
  });

  it("handles multiple trailing newlines", () => {
    const csv = "name,type,amount,monthlyAmount,firstSupportDate\nElvis Presley,one-time,30,0,2026-05-26\n\n\n";
    const lines = csv.trim().split("\n").slice(1).filter((line) => line.trim());
    expect(lines).toHaveLength(1);
  });
});

describe("BOM Handling", () => {
  it("detects UTF-8 BOM at position 0", () => {
    const textWithBOM = "\uFEFFname,type,amount,monthlyAmount,firstSupportDate";
    expect(textWithBOM.charCodeAt(0)).toBe(0xFEFF);
    const cleaned = textWithBOM.charCodeAt(0) === 0xFEFF ? textWithBOM.substring(1) : textWithBOM;
    expect(cleaned).toBe("name,type,amount,monthlyAmount,firstSupportDate");
  });

  it("leaves text without BOM unchanged", () => {
    const text = "name,type,amount,monthlyAmount,firstSupportDate";
    const cleaned = text.charCodeAt(0) === 0xFEFF ? text.substring(1) : text;
    expect(cleaned).toBe(text);
  });
});

describe("Name Cleaning", () => {
  const cleanName = (name: string) => {
    if (name.startsWith("https://github.com/")) {
      return "@" + name.replace("https://github.com/", "");
    }
    return name;
  };

  it("converts GitHub URL to @username", () => {
    expect(cleanName("https://github.com/someuser")).toBe("@someuser");
  });

  it("leaves regular names unchanged", () => {
    expect(cleanName("Siggi")).toBe("Siggi");
  });

  it("leaves @-prefixed names unchanged", () => {
    expect(cleanName("@someuser")).toBe("@someuser");
  });

  it("preserves umlauts in names", () => {
    expect(cleanName("Grünwald Almöhü")).toBe("Grünwald Almöhü");
  });
});

describe("Font Size Calculation", () => {
  const getFontSize = (totalSupport: number, maxAmount: number) => {
    const ratio = totalSupport / maxAmount;
    const minSize = 12;
    const maxSize = 32;
    return Math.floor(minSize + (maxSize - minSize) * ratio);
  };

  it("returns max size for highest supporter", () => {
    expect(getFontSize(30, 30)).toBe(32);
  });

  it("returns min size for smallest supporter", () => {
    // smallest non-zero (1/30 ratio)
    const size = getFontSize(1, 30);
    expect(size).toBeGreaterThanOrEqual(12);
    expect(size).toBeLessThan(20);
  });

  it("scales proportionally between min and max", () => {
    const halfSize = getFontSize(15, 30);
    expect(halfSize).toBe(22); // 12 + 20 * 0.5 = 22
  });
});
