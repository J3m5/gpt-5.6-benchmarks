type SvgAttributes = Record<string, string | number>;

interface ElementConstructor<T extends Element> {
  new (): T;
}

const svgNamespace = "http://www.w3.org/2000/svg";

export const gridStyles = {
  axis: { stroke: "#d4d7dc", width: 0.9 },
  minor: { stroke: "#eef0f2", width: 0.65 },
};

export function byId<T extends Element>(id: string, expectedType: ElementConstructor<T>): T {
  const element = document.getElementById(id);
  if (!(element instanceof expectedType)) {
    throw new TypeError(`Missing or invalid required element #${id}`);
  }
  return element;
}

export function query<T extends Element>(
  root: ParentNode,
  selector: string,
  expectedType: ElementConstructor<T>,
): T {
  const element = root.querySelector(selector);
  if (!(element instanceof expectedType)) {
    throw new TypeError(`Missing or invalid required element ${selector}`);
  }
  return element;
}

export function svgNode<K extends keyof SVGElementTagNameMap>(
  name: K,
  attributes: SvgAttributes = {},
  text = "",
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(svgNamespace, name);
  Object.entries(attributes).forEach(([key, value]) => {
    node.setAttribute(key, String(value));
  });
  if (text) {
    node.textContent = text;
  }
  return node;
}
