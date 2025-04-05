document.addEventListener('DOMContentLoaded', () => {
    const productGrid = document.getElementById('product-grid');
    const categoryList = document.getElementById('category-list');
    const paginationControls = document.getElementById('pagination-controls');

    // Ensure elements exist before proceeding
    if (!productGrid || !categoryList || !paginationControls) {
        console.error('Required elements (product grid, category list, or pagination controls) not found.');
        return;
    }

    const allProductCards = Array.from(productGrid.children); // Get all initial product cards
    let currentFilter = 'all';
    let currentPage = 1;
    const itemsPerPage = 8; // Adjust as needed

    // --- Filtering Logic ---
    const filterProducts = () => {
        // 1. Update active button style
        categoryList.querySelectorAll('button').forEach(button => {
            button.classList.remove('active');
            if (button.dataset.filter === currentFilter) {
                button.classList.add('active');
            }
        });

        // 2. Filter visibility based on currentFilter
        allProductCards.forEach(card => {
            const categories = card.dataset.category ? card.dataset.category.split(' ') : [];
            const matchesFilter = currentFilter === 'all' || categories.includes(currentFilter);

            // Hide or show based *only* on filter first
            card.classList.toggle('hidden', !matchesFilter);
        });

         // 3. Reset to page 1 and apply pagination to the *newly filtered* items
        currentPage = 1;
        applyPagination();
    };

    // Add event listener to category buttons
    categoryList.addEventListener('click', (event) => {
        if (event.target.tagName === 'BUTTON' && event.target.dataset.filter) {
            currentFilter = event.target.dataset.filter;
            filterProducts();
        }
    });


    // --- Pagination Logic ---
    const applyPagination = () => {
        // Get only the cards currently *visible* after filtering
        const visibleCards = allProductCards.filter(card => !card.classList.contains('hidden'));
        const totalItems = visibleCards.length;
        const totalPages = Math.ceil(totalItems / itemsPerPage);

        // Hide all visible cards initially (before showing the current page's cards)
        visibleCards.forEach(card => card.classList.add('hidden'));

        // Calculate cards for the current page
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const cardsToShow = visibleCards.slice(startIndex, endIndex);

        // Show only the cards for the current page
        cardsToShow.forEach(card => card.classList.remove('hidden'));

        // Update pagination controls
        renderPaginationControls(totalPages);
    };

    const renderPaginationControls = (totalPages) => {
        paginationControls.innerHTML = ''; // Clear existing controls

        if (totalPages <= 1) return; // No controls needed for 1 page

        // Previous Button
        const prevButton = document.createElement('button');
        prevButton.innerHTML = '« Prev';
        prevButton.disabled = currentPage === 1;
        prevButton.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                applyPagination();
            }
        });
        paginationControls.appendChild(prevButton);

        // Page Number Indicators (simplified for brevity, could add more complex logic for many pages)
        for (let i = 1; i <= totalPages; i++) {
            const pageSpan = document.createElement('span');
            pageSpan.textContent = i;
            if (i === currentPage) {
                pageSpan.classList.add('active');
            } else {
                pageSpan.addEventListener('click', () => {
                    currentPage = i;
                    applyPagination();
                });
            }
            paginationControls.appendChild(pageSpan);
        }

        // Next Button
        const nextButton = document.createElement('button');
        nextButton.innerHTML = 'Next »';
        nextButton.disabled = currentPage === totalPages;
        nextButton.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                applyPagination();
            }
        });
        paginationControls.appendChild(nextButton);
    };

    // --- Initial Setup ---
    // Apply initial filter (which is 'all') and pagination on load
    filterProducts(); // This will also call applyPagination
});
