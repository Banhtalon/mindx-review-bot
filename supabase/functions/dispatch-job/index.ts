/* global Deno */

import { createDispatchDependencies, type DispatchAdapterConfig } from "../_shared/edgeAdapters.ts";
import { loadDispatchEnvironment } from "../_shared/environment.ts";
import { createDispatchHttpHandler } from "../_shared/http.ts";

const environment = loadDispatchEnvironment(Deno.env);
const adapterConfig: DispatchAdapterConfig = environment;
const handler = createDispatchHttpHandler(
  createDispatchDependencies(adapterConfig),
  environment,
);

Deno.serve(handler);
