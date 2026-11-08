// Prints Kobo (the drawn SVG version) as static markup, for the email images. Bundled and run by email_assets.py.
import { renderToStaticMarkup } from 'react-dom/server';
import Kobo from '../../../frontend/src/components/Kobo';

const mood = (process.argv[2] ?? 'happy') as Parameters<typeof Kobo>[0]['mood'];
process.stdout.write(renderToStaticMarkup(<Kobo mood={mood} size={120} engine="svg" />));
