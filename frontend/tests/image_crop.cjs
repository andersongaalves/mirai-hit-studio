const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/css/main.css"></head><body>
<form><label>Capa<input type="file" name="capa" accept="image/png"></label><button type="submit">Enviar</button></form>
<script type="module">
import { bindImageCrop } from '/js/modules/image_crop.js';
import { uploadBusy } from '/js/modules/upload_feedback.js';
window.ratio=16/9; window.posts=0;
const input=document.querySelector('input');
bindImageCrop(input,{ratio:window.ratio});
document.querySelector('form').onsubmit=event=>{event.preventDefault();window.posts++;window.finish=uploadBusy(document.querySelector('button'));};
window.ready=true;
</script></body></html>`;
(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors=[];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', async route => {
        const url=new URL(route.request().url());
        if(url.pathname==='/crop-test')return route.fulfill({contentType:'text/html',body:html});
        if(url.origin!=='http://localhost:4173')return route.fulfill({body:''});
        const file=path.resolve(root,'.'+url.pathname);
        assert.ok(file.startsWith(root+path.sep));
        return route.fulfill({body:await fs.readFile(file),contentType:file.endsWith('.js')?'text/javascript':'text/css'});
    });
    try {
        await page.goto('http://localhost:4173/crop-test');
        await page.waitForFunction(()=>window.ready);
        const data=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=800;c.height=600;const x=c.getContext('2d');x.fillStyle='#009fc4';x.fillRect(0,0,400,600);x.fillStyle='#ed4784';x.fillRect(400,0,400,600);return c.toDataURL().split(',')[1];});
        const picker=page.getByLabel('Capa');
        await picker.setInputFiles({name:'cover.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')});
        const dialog=page.getByRole('dialog',{name:'Ajustar imagem'});
        const apply=dialog.getByRole('button',{name:'Usar corte'});
        await apply.waitFor();
        await page.waitForFunction(()=>!document.querySelector('[data-apply]').disabled);
        await page.evaluate(()=>document.querySelector('form').requestSubmit());
        assert.equal(await page.evaluate(()=>window.posts),0,'No upload while crop is pending');
        const screenDir=path.join(os.tmpdir(),'mirai-image-crop');await fs.mkdir(screenDir,{recursive:true});
        for(const width of [1280,390]){
            await page.setViewportSize({width,height:844});
            assert.equal(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth),true);
            await page.screenshot({path:path.join(screenDir,`crop-${width}.png`)});
        }
        await dialog.getByRole('slider',{name:'Zoom'}).fill('1.5');
        const handle=dialog.locator('.cropper-point.point-se');
        const box=await handle.boundingBox();
        await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x-30,box.y-10);await page.mouse.up();
        const crop=await dialog.locator('.cropper-crop-box').boundingBox();
        assert.ok(Math.abs(crop.width/crop.height-16/9)<0.03,'Crop shape remains fixed');
        await apply.click();await dialog.waitFor({state:'detached'});
        await page.waitForFunction(()=>!document.querySelector('input[type=file]').dataset.cropPending);
        const first=await picker.evaluate(async el=>Array.from(new Uint8Array(await el.files[0].arrayBuffer())));
        const png=Buffer.from(first);assert.equal(png.readUInt32BE(16),1600);assert.equal(png.readUInt32BE(20),900);
        await picker.setInputFiles({name:'other.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')});
        await dialog.getByRole('button',{name:'Cancelar'}).click();await dialog.waitFor({state:'detached'});
        await page.waitForFunction(()=>!document.querySelector('input[type=file]').dataset.cropPending);
        assert.deepEqual(await picker.evaluate(async el=>Array.from(new Uint8Array(await el.files[0].arrayBuffer()))),first,'Cancel restores previous image');
        await page.getByRole('button',{name:'Enviar',exact:true}).click();
        const busy=page.getByRole('button',{name:'Enviando...'});
        assert.equal(await busy.isDisabled(),true);assert.equal(await busy.getAttribute('aria-busy'),'true');
        assert.notEqual(await busy.evaluate(el=>getComputedStyle(el,'::before').animationName),'none');
        await page.evaluate(()=>window.finish());
        assert.equal(await page.getByRole('button',{name:'Enviar',exact:true}).isEnabled(),true);
        assert.deepEqual(errors,[]);
        console.log(`PASS: fixed crop, resize, zoom, cancellation, pending upload block and loading feedback; screenshots=${screenDir}`);
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
