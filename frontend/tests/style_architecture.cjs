const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const htmlFiles = fs.readdirSync(root).filter(name => name.endsWith('.html'));
const cssFiles = [];
const pending = [path.join(root, 'css')];
while (pending.length) {
    const directory = pending.pop();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory()) pending.push(file);
        else if (entry.name.endsWith('.css')) cssFiles.push(file);
    }
}

function localAsset(sourceFile, reference) {
    if (/^(?:https?:|data:|#)/i.test(reference)) return null;
    const pathname = decodeURIComponent(reference.split(/[?#]/, 1)[0]);
    const file = pathname.startsWith('/')
        ? path.resolve(root, '.' + pathname)
        : path.resolve(path.dirname(sourceFile), pathname);
    assert.ok(file.startsWith(root + path.sep), `${sourceFile}: asset outside frontend: ${reference}`);
    assert.ok(fs.existsSync(file), `${sourceFile}: missing asset: ${reference}`);
    return file;
}

let links = 0;
for (const name of htmlFiles) {
    const file = path.join(root, name);
    const html = fs.readFileSync(file, 'utf8');
    for (const match of html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"/g)) {
        localAsset(file, match[1]);
        links++;
    }
    for (const match of html.matchAll(/<script\b[^>]*src="([^"]+)"/g)) {
        localAsset(file, match[1]);
        links++;
    }
}

for (const file of cssFiles) {
    const css = fs.readFileSync(file, 'utf8');
    for (const match of css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
        localAsset(file, match[1]);
    }
}

let imports = 0;
const jsPending = [path.join(root, 'js')];
while (jsPending.length) {
    const directory = jsPending.pop();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory()) { jsPending.push(file); continue; }
        if (!entry.name.endsWith('.js')) continue;
        const source = fs.readFileSync(file, 'utf8');
        for (const match of source.matchAll(/\b(?:from\s*|import\s*\(\s*|import\s*)["'](\.[^"']+)["']/g)) {
            localAsset(file, match[1]);
            imports++;
        }
        for (const match of source.matchAll(/new URL\(\s*["'](\.[^"']+)["']\s*,\s*import\.meta\.url/g)) {
            localAsset(file, match[1]);
            imports++;
        }
    }
}

const styles = name => fs.readFileSync(path.join(root, name), 'utf8');
const client = styles('portal-cliente.html');
const producer = styles('portal-produtor.html');
const admin = styles('admin.html');
const main = styles('css/main.css');
for (const name of ['404.html', 'index.html', 'artists.html', 'creators.html', 'media-games.html', 'portfolio.html', 'calculadora.html', 'checkout.html']) {
    assert.match(styles(name), /css\/layout\.css/);
    assert.match(styles(name), /css\/pages\/public\.css/);
}
assert.doesNotMatch(main, /(?:layout|pages\/public)\.css/);
assert.doesNotMatch(admin, /css\/pages\/public\.css/);
assert.match(client, /\/css\/layouts\/portal-base\.css/);
assert.match(producer, /\/css\/layouts\/portal-base\.css/);
assert.doesNotMatch(client, /\/css\/pages\/produtor\.css/);
assert.match(producer, /\/css\/pages\/produtor\.css/);
assert.match(admin, /css\/pages\/integrado-admin\.css/);
assert.doesNotMatch(styles('css/integrado.css'), /\.(?:home-page|portfolio-page|quote-page|checkout-page|integrado-admin|integrado-portal)\b/);

console.log(`PASS: ${htmlFiles.length} HTML entries, ${cssFiles.length} CSS modules, ${links} HTML references and ${imports} JS imports resolve; portal styles stay scoped.`);
