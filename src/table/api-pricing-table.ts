import { apiPricingRows, apiPricingSources } from "../data";
import type { ApiPricingRow } from "../types";
import { byId } from "../utils/dom";

const priceFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

type PriceField =
  | "inputUsdPerMillionTokens"
  | "cachedInputUsdPerMillionTokens"
  | "outputUsdPerMillionTokens";

function priceTier(value: number, label?: string): HTMLSpanElement {
  const tier = document.createElement("span");
  tier.className = "price-tier";

  const price = document.createElement("span");
  price.textContent = priceFormatter.format(value);
  tier.append(price);

  if (label) {
    const context = document.createElement("small");
    context.textContent = label;
    tier.append(context);
  }
  return tier;
}

function appendTieredPrice(
  cell: HTMLTableCellElement,
  row: ApiPricingRow,
  field: PriceField,
): void {
  const longContext = row.longContextPricing;
  if (!longContext) {
    cell.append(priceTier(row[field]));
    return;
  }

  const threshold = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 0,
  }).format(longContext.thresholdTokens);
  cell.append(
    priceTier(row[field], `≤ ${threshold}`),
    priceTier(longContext[field], `> ${threshold}`),
  );
}

function modelCell(row: ApiPricingRow): HTMLTableCellElement {
  const cell = document.createElement("td");
  cell.className = "pricing-model";

  const name = document.createElement("strong");
  name.textContent = row.model;
  const provider = document.createElement("span");
  provider.textContent = row.provider;
  cell.append(name, provider);

  if (row.pricingModel) {
    const alias = document.createElement("small");
    alias.textContent = `Uses ${row.pricingModel} pricing`;
    cell.append(alias);
  }
  return cell;
}

function pricingCell(row: ApiPricingRow, field: PriceField): HTMLTableCellElement {
  const cell = document.createElement("td");
  cell.className = "numeric pricing-value";
  appendTieredPrice(cell, row, field);
  return cell;
}

function cacheWriteCell(row: ApiPricingRow): HTMLTableCellElement {
  const cell = document.createElement("td");
  cell.className = "numeric pricing-value";

  if (row.cacheWriteUsdPerMillionTokens === null || row.cacheWriteTtlMinutes === null) {
    const unavailable = document.createElement("span");
    unavailable.className = "not-applicable";
    unavailable.setAttribute("aria-label", "Not applicable");
    unavailable.textContent = "—";
    cell.append(unavailable);
    return cell;
  }

  cell.append(priceTier(row.cacheWriteUsdPerMillionTokens, `${row.cacheWriteTtlMinutes} min`));
  return cell;
}

function sourceLink(label: string, href: string): HTMLAnchorElement {
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = label;
  return link;
}

export function renderApiPricingTable(): void {
  const body = byId("api-pricing-body", HTMLTableSectionElement);
  body.replaceChildren(
    ...apiPricingRows.map((row) => {
      const tableRow = document.createElement("tr");
      tableRow.append(
        modelCell(row),
        pricingCell(row, "inputUsdPerMillionTokens"),
        pricingCell(row, "cachedInputUsdPerMillionTokens"),
        cacheWriteCell(row),
        pricingCell(row, "outputUsdPerMillionTokens"),
      );
      return tableRow;
    }),
  );

  const sources = byId("api-pricing-sources", HTMLSpanElement);
  sources.replaceChildren(
    sourceLink("OpenAI", apiPricingSources.openai.url),
    document.createTextNode(", "),
    sourceLink("Anthropic", apiPricingSources.anthropic.cacheUrl),
    document.createTextNode(", "),
    sourceLink("Google", apiPricingSources.google.url),
    document.createTextNode(", and "),
    sourceLink("LiteLLM", apiPricingSources.litellm.url),
  );
}
