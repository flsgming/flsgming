import os
import re
import sys

def replace_once(path, old, new, label):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if new in text:
        print(f"[SKIP] {label}")
        return
    if old not in text:
        raise RuntimeError(f"[FAIL] Anchor not found: {label} in {path}")
    text = text.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[OK] {label}")

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "src"

    # 1. dm/ios/Sources/main.m: cho phep A16 vao game
    main_m = os.path.join(root, "dm/ios/Sources/main.m")
    replace_once(
        main_m,
        "    if (gpu.supportsBCTextureCompression) return NULL;",
        '    if (gpu.supportsBCTextureCompression) return NULL;\n'
        '    fprintf(stderr, "boot: %s lacks hardware BC; enabling software BC fallback (A16)\\n", gpu ? gpu.name.UTF8String : "Metal");\n'
        '    return NULL;',
        "main.m: bypass A16 device block"
    )

    # 2. dm/gfx/tex/nvn_fmt_mtl.h
    fmt_h = os.path.join(root, "dm/gfx/tex/nvn_fmt_mtl.h")
    with open(fmt_h, "r", encoding="utf-8") as f:
        txt = f.read()
    if "nvn_fmt_set_bc_supported" not in txt:
        txt += "\nvoid nvn_fmt_set_bc_supported(int supported);\nint nvn_fmt_is_bc_supported(void);\n"
        with open(fmt_h, "w", encoding="utf-8") as f:
            f.write(txt)
        print("[OK] nvn_fmt_mtl.h")

    # 3. dm/gfx/tex/nvn_fmt_mtl.c
    fmt_c = os.path.join(root, "dm/gfx/tex/nvn_fmt_mtl.c")
    replace_once(
        fmt_c,
        '#include "nvn_fmt_mtl.h"',
        '#include "nvn_fmt_mtl.h"\n#include "nvn_bcdec.h"\n\n'
        'static int g_bc_supported = 1;\n'
        'void nvn_fmt_set_bc_supported(int supported) { g_bc_supported = supported; }\n'
        'int nvn_fmt_is_bc_supported(void) { return g_bc_supported; }',
        "nvn_fmt_mtl.c: include nvn_bcdec"
    )
    replace_once(
        fmt_c,
        "    if (f >= 0x79 && f <= 0x94) {",
        "    if (!g_bc_supported && nvn_is_bc_format(f)) {\n"
        "        uint32_t uncomp_mtl = nvn_bc_to_uncompressed_mtl(f);\n"
        "        if (uncomp_mtl) {\n"
        "            int no_alpha = (f == 0x41 || f == 0x45);\n"
        "            e = (ent){(uint16_t)uncomp_mtl, 2, (uint8_t)no_alpha, 0};\n"
        "        }\n"
        "    } else if (f >= 0x79 && f <= 0x94) {",
        "nvn_fmt_mtl.c: BC fallback mapping"
    )

    # 4. dm/gfx/nvn/nvn_mtl.m
    nvn_m = os.path.join(root, "dm/gfx/nvn/nvn_mtl.m")
    replace_once(
        nvn_m,
        '#include "../tex/nvn_fmt_mtl.h"',
        '#include "../tex/nvn_fmt_mtl.h"\n#include "../tex/nvn_bcdec.h"',
        "nvn_mtl.m: include nvn_bcdec.h"
    )
    replace_once(
        nvn_m,
        "static void mtl_init_once(void) {",
        "static int g_has_hardware_bc = 1;\nstatic void mtl_init_once(void) {",
        "nvn_mtl.m: g_has_hardware_bc"
    )
    replace_once(
        nvn_m,
        '    if (!g_dev.hasUnifiedMemory) MDIE("needs a unified-memory device (zero-copy memory pools)");',
        '    if (!g_dev.hasUnifiedMemory) MDIE("needs a unified-memory device (zero-copy memory pools)");\n'
        '#if TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR\n'
        '    g_has_hardware_bc = g_dev.supportsBCTextureCompression;\n'
        '#else\n'
        '    g_has_hardware_bc = 1;\n'
        '#endif\n'
        '    if (getenv("DM_FORCE_SW_BC")) g_has_hardware_bc = 0;\n'
        '    nvn_fmt_set_bc_supported(g_has_hardware_bc);\n'
        '    if (!g_has_hardware_bc) MLOG("[nvn-mtl] Device lacks hardware BC (A16); software BC fallback enabled");',
        "nvn_mtl.m: init g_has_hardware_bc"
    )
    replace_once(
        nvn_m,
        '    if (!g_dev.supportsBCTextureCompression) MDIE("the Metal device %s has no BC texture formats, which the games\' textures use and the host does not decompress: an iPhone needs an A17 Pro or later, an iPad an M1 or later", g_dev.name.UTF8String);',
        "    // A16 software BC fallback enabled via nvn_bcdec",
        "nvn_mtl.m: remove MDIE"
    )

    replace_once(
        nvn_m,
        '    int use_gpu = !linear && !rb_shift && g_nvn_deswz_gpu && (sparse ? spt != NULL : upsrc || mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo));\n'
        '    t_tex_upload_lookup = 0;\n'
        '    if (g_nvn_deswz_gpu && !use_gpu && !sparse && !rb_shift && !linear) RED_ONCE(40, "swizzled texture storage is not in a memory pool; falling back to the CPU");',
        '    int is_bc_fallback = !nvn_fmt_is_bc_supported() && nvn_is_bc_format(t->d.format);\n'
        '    int use_gpu = !is_bc_fallback && !linear && !rb_shift && g_nvn_deswz_gpu && (sparse ? spt != NULL : upsrc || mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo));\n'
        '    t_tex_upload_lookup = 0;\n'
        '    if (g_nvn_deswz_gpu && !use_gpu && !sparse && !rb_shift && !linear && !is_bc_fallback) RED_ONCE(40, "swizzled texture storage is not in a memory pool; falling back to the CPU");',
        "nvn_mtl.m: pkg_upload_ is_bc_fallback"
    )
    replace_once(
        nvn_m,
        '    id<MTLBuffer> stg = [g_dev newBufferWithLength:total ? total : 16 options:MTLResourceStorageModeShared];\n'
        '    res_add(stg); [g_up_keep addObject:stg];\n'
        '    size_t off = 0;',
        '    id<MTLBuffer> stg = [g_dev newBufferWithLength:total ? total : 16 options:MTLResourceStorageModeShared];\n'
        '    res_add(stg); [g_up_keep addObject:stg];\n'
        '    int uncomp_bpp = is_bc_fallback ? nvn_bc_decompressed_bpp(t->d.format) : 0;\n'
        '    size_t uncomp_total = 0;\n'
        '    if (is_bc_fallback) {\n'
        '        for (unsigned l = 0; l < d.mipmapLevelCount; l++) {\n'
        '            uint32_t w, h, z; tex_lsize(t, l, &w, &h, &z);\n'
        '            unsigned n = layers; if (need) { n = 0; for (unsigned y = 0; y < layers; y++) n += need[l * layers + y]; }\n'
        '            uncomp_total += (size_t)w * uncomp_bpp * h * z * n;\n'
        '        }\n'
        '    }\n'
        '    id<MTLBuffer> uncomp_stg = is_bc_fallback ? [g_dev newBufferWithLength:uncomp_total ? uncomp_total : 16 options:MTLResourceStorageModeShared] : nil;\n'
        '    if (uncomp_stg) { res_add(uncomp_stg); [g_up_keep addObject:uncomp_stg]; }\n'
        '    size_t off = 0, uncomp_off = 0;',
        "nvn_mtl.m: pkg_upload_ uncomp_stg alloc"
    )
    replace_once(
        nvn_m,
        '            up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);\n'
        '            off += pitch * rows * z;',
        '            if (is_bc_fallback) {\n'
        '                size_t uncomp_pitch = (size_t)w * uncomp_bpp;\n'
        '                size_t uncomp_img = uncomp_pitch * h;\n'
        '                for (uint32_t zi = 0; zi < z; zi++) {\n'
        '                    const uint8_t *src_slice = (const uint8_t *)stg.contents + off + zi * (pitch * rows);\n'
        '                    uint8_t *dst_slice = (uint8_t *)uncomp_stg.contents + uncomp_off + zi * uncomp_img;\n'
        '                    nvn_bc_decompress_level_strided(t->d.format, w, h, src_slice, pitch, dst_slice, uncomp_pitch);\n'
        '                }\n'
        '                up_blit_add(uncomp_stg, uncomp_off, uncomp_pitch, uncomp_img, MTLSizeMake(w, h, z), mt, y, l);\n'
        '                uncomp_off += uncomp_img * z;\n'
        '            } else {\n'
        '                up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);\n'
        '            }\n'
        '            off += pitch * rows * z;',
        "nvn_mtl.m: pkg_upload_ strided decompress loop"
    )

    with open(nvn_m, "r", encoding="utf-8") as f:
        nvn_txt = f.read()
    if "static void bc_decode_upload(" not in nvn_txt:
        m = re.search(r'^static void copy_b2t\([^\)]*\)\s*\{', nvn_txt, re.M)
        if not m:
            raise RuntimeError("[FAIL] copy_b2t signature not found")
        sig = m.group(0)
        bc_helpers = (
            'static int bc_source_ready(uint64_t addr, uint64_t size) {\n'
            '    if (!pend_hits(addr, size) && !g_sbw_over && !sbw_hits(addr, addr + size) && !gw_live(addr, addr + size)) return 1;\n'
            '    if (!gpu_read_wait(WS_DIAG)) return 0;\n'
            '    static int once; if (!once++) MLOG("software BC upload: waited for GPU-written source before decoding");\n'
            '    return 1;\n'
            '}\n'
            'static void bc_decode_upload(int f, uint32_t w, uint32_t h, int nz,\n'
            '                             const uint8_t *src, size_t src_img, size_t src_row,\n'
            '                             uint8_t *dst, size_t dst_img, size_t dst_row) {\n'
            '    static int requested = -1;\n'
            '    if (requested < 0) {\n'
            '        const char *e = getenv("DM_NVN_BC_THREADS");\n'
            '        int n = e ? atoi(e) : 0;\n'
            '        requested = n >= 1 && n <= 4 ? n : 0;\n'
            '    }\n'
            '    const size_t bytes = dst_img * (size_t)nz;\n'
            '    const uint32_t block_rows = (h + 3) / 4;\n'
            '    int workers = requested ? requested : bytes >= (16u << 20) ? 3 : bytes >= (4u << 20) ? 2 : 1;\n'
            '    if (workers > (int)block_rows) workers = (int)block_rows;\n'
            '    if (workers <= 1) {\n'
            '        for (int z = 0; z < nz; z++)\n'
            '            nvn_bc_decompress_level_strided(f, w, h, src + z * src_img, src_row, dst + z * dst_img, dst_row);\n'
            '        return;\n'
            '    }\n'
            '    const size_t lanes = (size_t)workers;\n'
            '    dispatch_apply(lanes * (size_t)nz, dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^(size_t job) {\n'
            '        size_t z = job / lanes, part = job % lanes;\n'
            '        uint32_t by0 = (uint32_t)((block_rows * part) / lanes);\n'
            '        uint32_t by1 = (uint32_t)((block_rows * (part + 1)) / lanes);\n'
            '        if (by1 == by0) return;\n'
            '        uint32_t y0 = by0 * 4;\n'
            '        uint32_t band_h = MIN(h - y0, (by1 - by0) * 4);\n'
            '        nvn_bc_decompress_level_strided(f, w, band_h,\n'
            '             src + z * src_img + (size_t)by0 * src_row, src_row,\n'
            '             dst + z * dst_img + (size_t)y0 * dst_row, dst_row);\n'
            '    });\n'
            '}\n'
        )
        nvn_txt = nvn_txt.replace(sig, bc_helpers + sig, 1)
        with open(nvn_m, "w", encoding="utf-8") as f:
            f.write(nvn_txt)
        print("[OK] nvn_mtl.m: added bc_source_ready + bc_decode_upload")

    with open(nvn_m, "r", encoding="utf-8") as f:
        nvn_txt = f.read()
    pos = nvn_txt.find("static void copy_b2t(")
    if pos < 0:
        raise RuntimeError("[FAIL] copy_b2t not found")
    target = "    id<MTL4ComputeCommandEncoder> b = blit();\n    if (is3d)"
    idx = nvn_txt.find(target, pos)
    if idx < 0:
        raise RuntimeError("[FAIL] target inside copy_b2t not found")
    if "if (!nvn_fmt_is_bc_supported() && nvn_is_bc_format(c->tex->d.format))" not in nvn_txt[pos:]:
        inject = (
            '    id<MTL4ComputeCommandEncoder> b = blit();\n'
            '    if (!nvn_fmt_is_bc_supported() && nvn_is_bc_format(c->tex->d.format)) {\n'
            '        if (!bc_source_ready(c->src, img * nz)) MDIE("software BC upload: GPU source did not complete");\n'
            '        if (!g_blit) b = blit();\n'
            '        int uncomp_bpp = nvn_bc_decompressed_bpp(c->tex->d.format);\n'
            '        size_t uncomp_row = (size_t)c->r.width * uncomp_bpp;\n'
            '        size_t uncomp_img = uncomp_row * c->r.height;\n'
            '        if (uncomp_bpp <= 0 || !uncomp_img || nz <= 0 || (size_t)nz > SIZE_MAX / uncomp_img)\n'
            '            MDIE("software BC upload: invalid decompressed size");\n'
            '        id<MTLBuffer> ub = [g_dev newBufferWithLength:uncomp_img * (size_t)nz options:MTLResourceStorageModeShared];\n'
            '        if (!ub || !ub.contents) MDIE("software BC upload: cannot allocate Metal buffer");\n'
            '        bc_decode_upload(c->tex->d.format, c->r.width, c->r.height, nz,\n'
            '                         (const uint8_t *)((__bridge id<MTLBuffer>)mb).contents + mo, img, row,\n'
            '                         (uint8_t *)ub.contents, uncomp_img, uncomp_row);\n'
            '        res_add(ub); defer_obj_release(ub);\n'
            '        if (is3d)\n'
            '            enc_b_copy_buffer_texture(b, ub, 0, uncomp_row, uncomp_img, MTLSizeMake(c->r.width, c->r.height, nz), t, 0, level, MTLOriginMake(c->r.xoffset, c->r.yoffset, c->r.zoffset));\n'
            '        else\n'
            '            for (int z = 0; z < nz; z++)\n'
            '                enc_b_copy_buffer_texture(b, ub, z * uncomp_img, uncomp_row, uncomp_img, MTLSizeMake(c->r.width, c->r.height, 1), t, layer0 + c->r.zoffset + z, level, MTLOriginMake(c->r.xoffset, c->r.yoffset, 0));\n'
            '        gsb_store_buf(c->tex, level, is3d ? (unsigned)c->r.zoffset : layer0 + (unsigned)c->r.zoffset, (unsigned)nz, &c->r, gsrc, grow, gimg);\n'
            '        if (paired) bcp_after(c->tex, level, &c->r);\n'
            '        return;\n'
            '    }\n'
            '    if (is3d)'
        )
        nvn_txt = nvn_txt[:idx] + inject + nvn_txt[idx + len(target):]
        with open(nvn_m, "w", encoding="utf-8") as f:
            f.write(nvn_txt)
        print("[OK] nvn_mtl.m: copy_b2t software BC path")

    # 5. Audit chi-doc: in ra cac duong upload texture khac (neu co) de de soi log
    print("[AUDIT] Texture upload/create call sites in nvn_mtl.m:")
    for lineno, line in enumerate(nvn_txt.splitlines(), 1):
        if any(k in line for k in ("up_blit_add(", "replaceRegion:", "newTextureWithDescriptor:offset:")):
            print(f"  L{lineno}: {line.strip()[:120]}")

if __name__ == "__main__":
    main()
