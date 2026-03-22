use std::env;
use std::fs;
use std::path::Path;

fn main() {
    // Embed the HTML template
    let out_dir = env::var_os("OUT_DIR").unwrap();
    let dest_path = Path::new(&out_dir).join("index.html");

    let html_content = include_str!("assets/index.html");
    fs::write(&dest_path, html_content).unwrap();

    println!("cargo:rerun-if-changed=assets/index.html");
}