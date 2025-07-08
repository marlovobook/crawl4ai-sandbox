#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import json
import yaml
import os
import sys
from pathlib import Path
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai.deep_crawling import DFSDeepCrawlStrategy

url_config = "https://process.gprocurement.go.th/egp2procmainWeb/jsp/procsearch.sch"

async def main():
    # Set UTF-8 encoding
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    # Load schema
    with open('config/css_schema.json', 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    # Create extraction strategy
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)
    
    # Create deep crawl strategy - removed verbose parameter
    deep_crawl_strategy = DFSDeepCrawlStrategy(
        max_depth=2,  # Reduced depth for testing
        include_external=False,  # Limit to internal links only
        max_pages=10  # Reduced for testing
    )
    
    # Configure browser
    browser_config = BrowserConfig(
        headless=True,
        verbose=True
    )
    
    # Configure crawler - ENABLE extraction strategy
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        deep_crawl_strategy=deep_crawl_strategy,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        verbose=True,
        # Add these to help with SPA crawling
        wait_for_images=True,
        page_timeout=60000,
        js_only=True,  # This helps with React/SPA sites
        delay_before_return_html=5.0,  # Wait 5 seconds for JS to render
        css_selector="body"  # Wait for body to be available
    )
    
    print("Starting deep crawl of TradeSquare website...")
    
    # Try crawling specific URLs manually if deep crawl doesn't find them
    urls_to_crawl = [
        "https://tradesquareltd.com/",
        "https://tradesquareltd.com/home",
        "https://tradesquareltd.com/our-story", 
        "https://tradesquareltd.com/our-works",
        "https://tradesquareltd.com/our-services",
        "https://tradesquareltd.com/careers",
        "https://tradesquareltd.com/contact-us"
    ]
    
    print("Starting crawl of TradeSquare website...")
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Try deep crawl first
        result = await crawler.arun(
            url="https://tradesquareltd.com/",
            config=run_config
        )
        
        # If deep crawl doesn't find many pages, try manual approach
        if isinstance(result, list) and len(result) < 3:
            print("🔄 Deep crawl found limited pages, trying manual URL crawling...")
            
            # Create config without deep crawl strategy for manual crawling
            manual_config = CrawlerRunConfig(
                extraction_strategy=extraction_strategy,
                remove_overlay_elements=True,
                cache_mode=CacheMode.BYPASS,
                verbose=True,
                wait_for_images=True,
                page_timeout=60000,
                js_only=True,
                delay_before_return_html=5.0,  # Wait 5 seconds for JS to render
                css_selector="body"  # Wait for body to be available
            )
            
            # Crawl each URL manually
            manual_results = []
            for url in urls_to_crawl:
                print(f"🌐 Manually crawling: {url}")
                try:
                    page_result = await crawler.arun(url=url, config=manual_config)
                    if page_result.success:
                        manual_results.append(page_result)
                        print(f"  ✅ Success: {url}")
                    else:
                        print(f"  ❌ Failed: {url} - {page_result.error_message}")
                except Exception as e:
                    print(f"  ❌ Error crawling {url}: {str(e)}")
            
            # Use manual results if we got more pages
            if len(manual_results) > len(result) if isinstance(result, list) else 1:
                result = manual_results
                print(f"🔄 Using manual crawl results ({len(manual_results)} pages)")
        
        # Handle results (list of results)
        if isinstance(result, list):
            print(f"✅ Crawl completed!")
            print(f"🌐 Crawled {len(result)} pages")
            
            successful_results = [r for r in result if r.success]
            failed_results = [r for r in result if not r.success]
            
            print(f"✅ Successful: {len(successful_results)}")
            if failed_results:
                print(f"❌ Failed: {len(failed_results)}")
            
            # Process each successful result
            all_extracted_content = []
            crawled_urls = []
            
            for i, page_result in enumerate(successful_results):
                crawled_urls.append(page_result.url)
                print(f"  {i+1}. {page_result.url}")
                
                # Debug: Check what content we have
                print(f"    - Has extracted_content: {page_result.extracted_content is not None}")
                if page_result.extracted_content:
                    print(f"    - Content length: {len(page_result.extracted_content)}")
                
                if page_result.extracted_content:
                    try:
                        content = json.loads(page_result.extracted_content)
                        if isinstance(content, list):
                            all_extracted_content.extend(content)
                        else:
                            all_extracted_content.append(content)
                    except json.JSONDecodeError:
                        # Handle non-JSON content
                        all_extracted_content.append({
                            "url": page_result.url,
                            "content": page_result.extracted_content
                        })
                else:
                    # If no extracted content, add a fallback entry
                    all_extracted_content.append({
                        "url": page_result.url,
                        "status": "no_extraction",
                        "markdown_preview": page_result.markdown[:200] + "..." if page_result.markdown else "No content"
                    })
            
            # Ensure output directory exists
            os.makedirs('output', exist_ok=True)
            
            # Save combined results
            output_path = 'output/deep_crawl_output.json'
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_extracted_content, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Results saved to: {output_path}")
            
            # Save individual page results
            detailed_output_path = 'output/deep_crawl_detailed.json'
            detailed_data = []
            for page_result in successful_results:
                page_data = {
                    "url": page_result.url,
                    "success": page_result.success,
                    "extracted_content": page_result.extracted_content,
                    "markdown": page_result.markdown[:500] + "..." if page_result.markdown and len(page_result.markdown) > 500 else page_result.markdown
                }
                detailed_data.append(page_data)
            
            with open(detailed_output_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_data, f, ensure_ascii=False, indent=2)
            print(f"📊 Detailed crawl data saved to: {detailed_output_path}")
            
            # Print summary
            if all_extracted_content:
                print(f"📄 Extracted {len(all_extracted_content)} items total")
                if all_extracted_content:
                    print("\n📋 Preview of extracted content:")
                    for i, item in enumerate(all_extracted_content[:3]):
                        if isinstance(item, dict):
                            title = item.get('title', item.get('name', item.get('url', 'No title')))
                            print(f"\n{i+1}. {title}")
                            if 'link' in item:
                                print(f"   🔗 {item['link']}")
                            if 'details' in item:
                                print(f"   📝 {str(item['details'])[:100]}...")
            
            # Print failed results if any
            if failed_results:
                print("\n❌ Failed URLs:")
                for failed_result in failed_results:
                    print(f"  - {failed_result.url}: {failed_result.error_message}")
            
        else:
            # Handle single result (fallback)
            if result.success:
                print(f"✅ Single page crawl successful!")
                # ... existing single result handling code ...
            else:
                print(f"❌ Crawl failed: {result.error_message}")
                return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
