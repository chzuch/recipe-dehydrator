/** hash 路由：#/ 菜谱库（默认），#/card/:id 卡片详情。 */

export type Route = { name: "library" } | { name: "card"; id: string };

export function parseRoute(): Route {
  const hash = location.hash.replace(/^#\/?/, "");
  if (hash.startsWith("card/")) {
    return { name: "card", id: hash.slice("card/".length) };
  }
  return { name: "library" };
}

export function navigate(route: Route): void {
  if (route.name === "library") {
    location.hash = "#/";
  } else {
    location.hash = `#/card/${route.id}`;
  }
}

export function onRouteChange(cb: (route: Route) => void): void {
  window.addEventListener("hashchange", () => cb(parseRoute()));
  cb(parseRoute());
}
