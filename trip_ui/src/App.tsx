import React from "react";
import MultiSessionApp from "./MultiSessionApp";

/**
 * TripPlanner UI — Multi-Session Chat Interface
 *
 * This is the main entry point that renders the multi-session chat interface.
 * Each session maintains its own conversation context and history.
 */

export default function App(): JSX.Element {
  return <MultiSessionApp />;
}
