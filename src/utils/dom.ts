interface ElementConstructor<T extends Element> {
  new (): T;
}

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
