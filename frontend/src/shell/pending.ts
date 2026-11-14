/** Building rules a country picker entry names (not in the API yet). */
export interface CountryRule {
  id: string;
  name: string;
  law: string;
}

// PENDING(Info.country_rules): mock until the backend adds it (#14)
export const PENDING_COUNTRY_RULES: CountryRule[] = [
  { id: 'fi', name: 'Finland', law: 'Building Act 751/2023' },
  { id: 'ch', name: 'Switzerland', law: 'Cantonal building law, SIA norms' },
];
